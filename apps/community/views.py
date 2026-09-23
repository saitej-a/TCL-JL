"""Community API views (T5.4-T5.11; 5.2 D1-D5, P5-P9; 04 §31-§44).

Surface contract highlights:

* **403 for foreign writes, 404 for writes into tombstones** (P6, P9): a post
  exists publicly, so ownership failures are `not_author` 403; a removed post
  stops accepting votes/comments/edits (`content_deleted` 404) while *staying*
  readable as a tombstone. Only GETs keep working on `is_deleted`.
* **409 for repeat votes** (`already_voted`): PostgreSQL's
  `unique_user_post_vote` is the guarantee (5.1 criterion 3); the API just
  translates `IntegrityError` so a race never becomes a 500.
* **`/unlock/` and `/unpin/` exist beyond 04 §37** — 08's reversibility
  principle and §38's own pin symmetry; flagged in the plan as an addition,
  not an oversight.
* **Query-count budgets** (COMM-08): the feed is capped at 3 queries (count +
  page + authors via `select_related`), the comment thread at 4 (count + page
  + replies + post author). These are regression guards, tested with
  `assertNumQueries`.
"""

import logging
from uuid import UUID

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerified
from apps.accounts.views import SpecErrorMixin
from apps.candidates.permissions import IsActive
from apps.community import views_services as svc
from apps.community.models import Announcement, Comment, Post
from apps.community.permissions import IsModerator
from apps.community.serializers import (
    AnnouncementPublicSerializer,
    AnnouncementWriteSerializer,
    CommentSerializer,
    CommentWriteSerializer,
    PostCardSerializer,
    PostWriteSerializer,
    VoteSerializer,
)
from apps.community.services import CommunityContentError, create_comment, create_post
from apps.community.throttles import CommunityWriteRateThrottle


def query_budget(limit: int):
    """COMM-08 regression guard, used by tests: assert a request used ≤ limit
    queries. Kept next to the views so the budget and the code it guards age
    together."""
    from contextlib import contextmanager

    @contextmanager
    def _budget():
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            yield
        if len(ctx.captured_queries) > limit:
            raise AssertionError(
                f"query budget exceeded: {len(ctx.captured_queries)} > {limit} (COMM-08 regression)"
            )

    return _budget()


# Orderings the API admits (04 §31 whitelist). `trending` ignores ?ordering=.
POST_ORDERINGS = {
    "newest": ("-is_pinned", "-created_at"),
    "oldest": ("-is_pinned", "created_at"),
    "votes": ("-is_pinned", "-vote_count", "-created_at"),
    "trending": ("-is_pinned", "-activity", "-created_at"),
}


class _InvalidCategory(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, value):
        super().__init__(
            {
                "error": {
                    "code": "invalid_category",
                    "message": f"Unknown category filter value: {value!r}.",
                }
            }
        )


class _InvalidOrdering(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, value):
        super().__init__(
            {
                "error": {
                    "code": "invalid_ordering",
                    "message": f"Unsupported ordering value: {value!r}.",
                }
            }
        )


class _ContentDeleted(APIException):
    """Writes into a tombstone: removed content is inert, not invisible (P9)."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self):
        super().__init__(
            {
                "error": {
                    "code": "content_deleted",
                    "message": "This content has been removed.",
                }
            }
        )


class _ContentNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, kind: str):
        super().__init__(
            {
                "error": {
                    "code": f"{kind}_not_found",
                    "message": f"{kind.capitalize()} not found.",
                }
            }
        )


class _DuplicateVote(APIException):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self):
        super().__init__(
            {
                "error": {
                    "code": "already_voted",
                    "message": "You have already voted on this post.",
                }
            }
        )


class _Locked(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self):
        super().__init__(
            {
                "error": {
                    "code": "post_locked",
                    "message": "This thread is locked; new comments are disabled.",
                }
            }
        )


class _ScamPatternDetected(APIException):
    """Pre-publication scam block (8.1 D1/D2 — hard refuse, never auto-publish).

    The message is heuristics.CATEGORY_MESSAGE: it names the violation category
    so honest users can fix false positives, and NEVER contains the matched
    regex (T-08.1-03: the pattern text is the evasion recipe).
    """

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self):
        from apps.moderation.heuristics import CATEGORY_MESSAGE

        super().__init__({"error": {"code": "scam_pattern_detected", "message": CATEGORY_MESSAGE}})


class _DuplicatePost(APIException):
    """60-minute duplicate-post debounce hit (T8.5 + 8.1 D6)."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self):
        super().__init__(
            {
                "error": {
                    "code": "duplicate_post",
                    "message": "You already posted this content recently.",
                }
            }
        )


class CommunityErrorMixin(SpecErrorMixin):
    """Translate service/Django exceptions into the project envelope, then let
    the accounts handler render them (3.2/4.2 precedent — one body style)."""

    def handle_exception(self, exc):
        if isinstance(exc, CommunityContentError):
            envelope = APIException({"error": {"code": exc.code, "message": str(exc)}})
            envelope.status_code = status.HTTP_400_BAD_REQUEST
            exc = envelope
        elif isinstance(exc, svc.DuplicateVoteError):
            exc = _DuplicateVote()
        return super().handle_exception(exc)


def _clean_uuid(value, kind: str) -> UUID:
    """Malformed identifiers 404 inside the envelope (F3 discipline) rather than
    surfacing Django's non-JSON 404 page.

    DRF's `<uuid:pk>` converter already delivers a UUID instance; `UUID(x)` on
    one raises AttributeError, so instances pass through untouched and only
    genuinely malformed strings convert-and-fail."""
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise _ContentNotFound(kind) from exc


def _get_live_post(pk: str, *, for_read: bool) -> Post:
    """Resolve a post inside the envelope.

    `for_read` keeps tombstones readable (P9); every mutating route passes
    `for_read=False` so a deleted post refuses writes with `content_deleted`.
    """
    post = (
        Post.objects.filter(id=_clean_uuid(pk, "post"))
        .select_related("author__candidate_profile")
        .first()
    )
    if post is None:
        raise _ContentNotFound("post")
    if not for_read and post.is_deleted:
        raise _ContentDeleted()
    return post


def _with_counts(post: Post, user=None) -> Post:
    """A freshly mutated post re-annotated so the response's card parity holds
    (counts + the caller's own vote flag without extra per-field queries)."""
    annotations, prefetch = svc._feed_annotations(user)
    queryset = Post.objects.select_related("author__candidate_profile")
    if prefetch is not None:
        queryset = queryset.prefetch_related(prefetch)
    return queryset.annotate(**annotations).get(id=post.id)


def _post_category_keys() -> set[str]:
    from apps.community.validators import post_categories

    return {key for key, _label in post_categories()}


def _scan_or_raise(title: str, body: str) -> None:
    """8.1 D1/D4: raise 400 scam_pattern_detected when the text matches a scam
    pattern. Called on all four write surfaces (post create/edit, comment
    create/edit); comments pass title=""."""
    from apps.moderation.heuristics import evaluate_content_safety

    if evaluate_content_safety(title, body)["flagged"]:
        raise _ScamPatternDetected()


class PostListCreateView(CommunityErrorMixin, ListAPIView):
    """`GET /api/v1/community/posts/` — the feed (04 §31-§35, T5.4-T5.6).

    Tabs: `tab=trending|newest|oldest|votes` (default newest — §31's
    chronology). `category=` and `search=` narrow; `?ordering=` is restricted
    to the §31 whitelist (`created_at|vote_count|comment_count`); an unknown
    category value 404s `invalid_category`, an unknown ordering 400s
    `invalid_ordering` (04 §31's error contract).
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    serializer_class = PostCardSerializer

    def get_queryset(self):
        params = self.request.query_params
        category = params.get("category") or None
        if category is not None and category not in _post_category_keys():
            raise _InvalidCategory(category)
        search = (params.get("search") or "").strip() or None

        tab = params.get("tab", "newest")
        if tab == "trending":
            queryset = svc.trending_queryset(self.request.user)
        else:
            queryset = svc.feed_queryset(self.request.user, category=category, search=search)
            queryset = queryset.order_by(*POST_ORDERINGS.get(tab, POST_ORDERINGS["newest"]))

        ordering = params.get("ordering")
        if ordering:
            key = ordering.lstrip("-")
            if key not in ("created_at", "vote_count", "comment_count"):
                raise _InvalidOrdering(ordering)
            # §31's whitelist with the requested direction; pinned threads keep
            # their precedence in every ordering.
            queryset = queryset.order_by("-is_pinned", ordering, "-created_at")
        return queryset

    def list(self, request, *args, **kwargs):
        # COMM-08's budget (3 queries: count + page + select_related authors) is
        # enforced by the test suite with assertNumQueries, not at runtime —
        # production request paths shouldn't pay for a guard only tests need.
        return super().list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """`POST /api/v1/community/posts/` (04 §32, T5.7).

        Phase 8.1 guard clauses BEFORE the write: scam-pattern scan (D1/D4) and
        the 60-minute duplicate debounce (D6 — title + body hashes, posts only).
        """
        serializer = PostWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data["title"]
        body = serializer.validated_data["body"]
        _scan_or_raise(title, body)
        from apps.moderation.debounce import check_duplicate_post, register_post_hashes

        if check_duplicate_post(request.user.id, title, body):
            raise _DuplicatePost()
        post = create_post(request.user, **serializer.validated_data)
        register_post_hashes(request.user.id, title, body)
        return Response(
            PostCardSerializer(_with_counts(post, request.user), context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PostDetailView(CommunityErrorMixin, APIView):
    """`GET/PATCH/DELETE /api/v1/community/posts/{id}/` (04 §35-§37, T5.8).

    GET works on tombstones (P9: detail renders the masked shape);
    PATCH/DELETE require authorship (403 for others) and refuse tombstones.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    throttle_classes = [CommunityWriteRateThrottle]

    def get(self, request, *args, **kwargs):
        post = _get_live_post(kwargs["pk"], for_read=True)
        return Response(
            PostCardSerializer(_with_counts(post, request.user), context={"request": request}).data
        )

    def patch(self, request, *args, **kwargs):
        post = _get_live_post(kwargs["pk"], for_read=False)
        _require_author(request, post)
        serializer = PostWriteSerializer(post, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field in ("title", "body", "category"):
            if field in serializer.validated_data:
                setattr(post, field, serializer.validated_data[field])
        # 8.1 D5: edits are scanned on the MERGED state — stored values overlaid
        # with the partial payload — so a clean post cannot be edited into a scam.
        _scan_or_raise(post.title, post.body)
        post.full_clean()
        post.save()
        return Response(
            PostCardSerializer(_with_counts(post, request.user), context={"request": request}).data
        )

    def delete(self, request, *args, **kwargs):
        post = _get_live_post(kwargs["pk"], for_read=False)
        _require_author(request, post)
        post.is_deleted = True  # flag only — originals stay in the row (08 §390)
        post.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostVoteView(CommunityErrorMixin, APIView):
    """`POST/DELETE /api/v1/community/posts/{id}/vote/` (04 §43, T5.9).

    One vote per (user, post) is *database* law (5.1); this route's guarantee
    is that the law surfaces as 409 `already_voted`, never a 500, even when two
    concurrent requests race each other to the constraint.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    throttle_classes = [CommunityWriteRateThrottle]

    def post(self, request, pk):
        post = _get_live_post(pk, for_read=False)
        try:
            svc.vote_post(request.user, post)
        except svc.DuplicateVoteError:
            raise _DuplicateVote() from None
        return Response(
            VoteSerializer(_with_counts(post, request.user), context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, pk):
        post = _get_live_post(pk, for_read=False)
        if not svc.unvote_post(request.user, post):
            raise _ContentNotFound("vote")
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentListCreateView(CommunityErrorMixin, APIView):
    """`GET/POST /api/v1/community/posts/{id}/comments/` (04 §39-§42, T5.10-T5.11).

    GET paginates top-level comments chronologically with replies nested one
    level deep (04 §40); `total_comments` counts **all** comments including
    tombstones (D4) so the card's number matches the thread — while `count`
    stays the honest top-level pagination count.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    throttle_classes = [CommunityWriteRateThrottle]

    def get(self, request, *args, **kwargs):
        post = _get_live_post(kwargs["pk"], for_read=True)
        page_size = _page_size(request)
        page = svc.comment_page(post, page_size=page_size, offset=_offset(request, page_size))
        serializer = CommentSerializer(
            page["comments"],
            many=True,
            context={"request": request, "replies_by_parent": page["replies_by_parent"]},
        )
        return Response(
            {
                "count": page["total_top_level"],
                "total_comments": Comment.objects.filter(post=post).count(),
                "results": serializer.data,
            }
        )

    def post(self, request, *args, **kwargs):
        post = _get_live_post(kwargs["pk"], for_read=False)
        if post.is_locked:
            raise _Locked()
        serializer = CommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # 8.1 D4: comments are scanned on create (never debounced, D6).
        _scan_or_raise("", serializer.validated_data["body"])
        parent = _resolve_parent(post, serializer.validated_data.get("parent_id"))
        comment = create_comment(
            post,
            request.user,
            body=serializer.validated_data["body"],
            parent=parent,
        )
        return Response(
            CommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CommentDetailView(CommunityErrorMixin, APIView):
    """`GET/PATCH/DELETE /api/v1/community/comments/{id}/` (04 §44, T5.11).

    GET is a flat single-comment read (replies live under the thread route).
    PATCH/DELETE are author-only (403 for others); a tombstone stays readable
    and refuses writes like a deleted post.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    throttle_classes = [CommunityWriteRateThrottle]

    def _get_comment(self, pk: str, *, for_read: bool) -> Comment:
        comment = (
            Comment.objects.filter(id=_clean_uuid(pk, "comment"))
            .select_related("author__candidate_profile", "post")
            .first()
        )
        if comment is None:
            raise _ContentNotFound("comment")
        if not for_read and comment.is_deleted:
            raise _ContentDeleted()
        return comment

    def get(self, request, *args, **kwargs):
        comment = self._get_comment(kwargs["pk"], for_read=True)
        return Response(CommentSerializer(comment, context={"request": request}).data)

    def patch(self, request, *args, **kwargs):
        comment = self._get_comment(kwargs["pk"], for_read=False)
        _require_author(request, comment)
        serializer = CommentWriteSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        comment.body = serializer.validated_data["body"]
        # 8.1 D5: comment edits scanned on the merged state, before save.
        _scan_or_raise("", comment.body)
        comment.full_clean()
        comment.save(update_fields=["body", "updated_at"])
        return Response(CommentSerializer(comment, context={"request": request}).data)

    def delete(self, request, *args, **kwargs):
        comment = self._get_comment(kwargs["pk"], for_read=False)
        _require_author(request, comment)
        comment.is_deleted = True
        comment.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostLockView(CommunityErrorMixin, APIView):
    """`POST /api/v1/community/posts/{id}/lock/` (04 §38) and `/unlock/`
    (addition beyond §37: 08's reversibility principle). Staff-only — the
    author cannot lock their own thread against other candidates (P8)."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]
    throttle_classes = [CommunityWriteRateThrottle]

    def post(self, request, pk):
        return self._set_locked(pk, True)

    def delete(self, request, pk):
        return self._set_locked(pk, False)

    def _set_locked(self, pk, locked: bool):
        post = _get_live_post(pk, for_read=False)
        post.is_locked = locked
        post.save(update_fields=["is_locked", "updated_at"])
        return Response(
            VoteSerializer(
                _with_counts(post, self.request.user), context={"request": self.request}
            ).data
        )


class PostPinView(CommunityErrorMixin, APIView):
    """`POST/DELETE /api/v1/community/posts/{id}/pin/` (04 §38's symmetry).
    Staff-only, same rationale as lock."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]
    throttle_classes = [CommunityWriteRateThrottle]

    def post(self, request, pk):
        return self._set_pinned(pk, True)

    def delete(self, request, pk):
        return self._set_pinned(pk, False)

    def _set_pinned(self, pk, pinned: bool):
        post = _get_live_post(pk, for_read=False)
        post.is_pinned = pinned
        post.save(update_fields=["is_pinned", "updated_at"])
        return Response(
            VoteSerializer(
                _with_counts(post, self.request.user), context={"request": self.request}
            ).data
        )


def _require_author(request, content) -> None:
    if content.author_id != request.user.id:
        raise PermissionDenied(
            detail={
                "error": {
                    "code": "not_author",
                    "message": "Only the author can modify this content.",
                }
            }
        )


def _resolve_parent(post: Post, parent_id) -> Comment | None:
    if parent_id is None:
        return None
    parent = (
        Comment.objects.filter(id=parent_id, post=post)
        .select_related("author__candidate_profile")
        .first()
    )
    if parent is None:
        # Foreign or nonexistent parent — same verdict either way.
        raise _ContentNotFound("comment")
    return parent


def _page_size(request) -> int:
    # The global paginator has no page_size_query_param, so ?page_size= is
    # ignored — same "controlled maximum" reasoning as 4.2's list route.
    return 20


def _offset(request, page_size: int) -> int:
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
    except ValueError:
        page = 1
    return (page - 1) * page_size


# --- Announcements (Phase 8.2 — T8.6/T8.10, 04 §71–§75) --------------------------


class AnnouncementNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self):
        super().__init__(
            {"error": {"code": "announcement_not_found", "message": "Announcement not found."}}
        )


def _get_announcement(pk):
    """Resolve an announcement or raise the JSON 404 envelope."""
    try:
        announcement_id = UUID(str(pk))
    except (TypeError, ValueError):
        raise AnnouncementNotFound() from None
    announcement = Announcement.objects.filter(pk=announcement_id).first()
    if announcement is None:
        raise AnnouncementNotFound()
    return announcement


def _wants_publish(payload) -> bool:
    value = payload.get("is_published")
    return value in (True, 1, "1", "true", "True")


class AnnouncementListCreateView(CommunityErrorMixin, APIView):
    """`GET /api/v1/announcements/` (04 §72) + `POST` (04 §73).

    Read is anonymous: 04 §72 says "public or authenticated depending on UI
    requirements" and the Phase 9 landing/feed renders pinned advisories before
    login. Write is staff-only and always creates a *draft* — publication is the
    `publish()` transition (§73's POST body has no is_published field).
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsActive(), IsVerified(), IsModerator()]
        return [AllowAny()]

    def get(self, request):
        now = timezone.now()
        queryset = Announcement.objects.filter(is_published=True).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AnnouncementPublicSerializer(page, many=True).data)

    def post(self, request):
        serializer = AnnouncementWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save(created_by=request.user)
        return Response(
            _announcement_payload(announcement),
            status=status.HTTP_201_CREATED,
        )


class AnnouncementDetailView(CommunityErrorMixin, APIView):
    """`PATCH`/`DELETE /api/v1/announcements/{id}/` (04 §74–§75). Staff-only.

    A PATCH carrying `is_published: true` publishes *through* `publish()` so the
    broadcast dispatches exactly once (an already-published row is a no-op), and
    ordinary field edits never re-broadcast.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]

    def patch(self, request, pk):
        announcement = _get_announcement(pk)
        serializer = AnnouncementWriteSerializer(announcement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        published_now = _wants_publish(request.data)
        if published_now:
            announcement.publish()
        return Response(_announcement_payload(announcement))

    def delete(self, request, pk):
        announcement = _get_announcement(pk)
        announcement_id = str(announcement.pk)
        # §75 permits real deletion for announcements; the audit line is the log.
        announcement.delete()
        logging.getLogger("community").info(
            "ANNOUNCEMENT_DELETED id=%s by=%s", announcement_id, request.user.pk
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnnouncementPublishView(CommunityErrorMixin, APIView):
    """`POST /api/v1/announcements/{id}/publish/` — the explicit publish trigger.

    202 when this call published (the fan-out is async, the D1 response style);
    200 when the row was already published, so the caller can tell the two apart
    without a second broadcast ever firing.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]

    def post(self, request, pk):
        announcement = _get_announcement(pk)
        published_now = announcement.publish()
        return Response(
            {
                "id": announcement.id,
                "is_published": announcement.is_published,
                "detail": "broadcast scheduled" if published_now else "already published",
            },
            status=status.HTTP_202_ACCEPTED if published_now else status.HTTP_200_OK,
        )


def _announcement_payload(announcement) -> dict:
    """Public shape + `is_published` for staff-facing responses."""
    payload = dict(AnnouncementPublicSerializer(announcement).data)
    payload["is_published"] = announcement.is_published
    return payload
