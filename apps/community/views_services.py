"""Community read services (5.2 R1-R4; 04 §31-§35).

Feed composition lives here so the view stays a thin adapter and the query
strategy is testable in isolation. Two invariants are structural:

* **No row multiplication.** Counting two reverse FKs in one `annotate` joins
  and multiplies rows (3 votes × 2 comments ⇒ 6/6) unless each count is
  `distinct=True` — which is exact even over the multiplied rows, so every
  count and the activity sum stay correct.
* **No N+1.** Authors (with their profile, for the cohort fields and the
  avatar seed) arrive in one `select_related`; comment replies are assembled
  in memory from one page query.
"""

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.community.models import Comment, Post


def websearch_query(term: str):
    """D2's query parser: websearch_to_query supports quoted phrases and the
    OR / minus operators candidates actually type."""
    from django.contrib.postgres.search import SearchQuery

    return SearchQuery(term, search_type="websearch")


def _window_start():
    return timezone.now() - timezone.timedelta(days=getattr(settings, "TRENDING_WINDOW_DAYS", 14))


def _feed_annotations(user):
    """Counts as `distinct=True` annotations plus the caller's own vote slice.

    Counting two reverse FKs in one `annotate` joins and multiplies rows
    (3 votes × 2 comments ⇒ 6/6) — `distinct=True` is what keeps both counts
    exact (COMM-08's trap). `has_voted` is a **filtered** Prefetch of only the
    caller's vote rows: a plain `exists()` per card would be an N+1 that the
    distinct annotations alone don't fix.
    """
    from django.db.models import Prefetch

    from apps.community.models import PostVote

    annotations = {
        "vote_count": Count("votes", distinct=True),
        "comment_count": Count("comments", distinct=True),
    }
    if user is None or not user.is_authenticated:
        return annotations, None
    prefetch = Prefetch(
        "votes",
        queryset=PostVote.objects.filter(user=user),
        to_attr="user_votes",
    )
    return annotations, prefetch


def feed_queryset(user, category: str | None = None, search: str | None = None) -> QuerySet[Post]:
    """R3 + D2: search uses an on-the-fly `SearchVector` over title+body — no
    column, no migration, no staleness (a stored tsvector + GIN index stays a
    purely additive upgrade). Filters narrow; ordering decides, so there is no
    relevance ranking and pagination stays predictable."""
    from django.contrib.postgres.search import SearchVector

    annotations, prefetch = _feed_annotations(user)
    queryset = Post.objects.select_related("author__candidate_profile")
    if prefetch is not None:
        queryset = queryset.prefetch_related(prefetch)
    if annotations:
        queryset = queryset.annotate(**annotations)
    if category:
        queryset = queryset.filter(category=category)
    if search:
        vector = SearchVector("title", weight="A") + SearchVector("body", weight="B")
        queryset = queryset.annotate(search=vector).filter(search=websearch_query(search))
    return queryset


def trending_queryset(user) -> QuerySet[Post]:
    """D1: windowed activity score (votes + comments), pinned first, then the
    score, then newest-first tiebreak (04 §31's trend order, R1's window).

    The window *filters*: posts with zero in-window activity are absent from
    the tab entirely, not ranked zero — a wall of dead threads cannot occupy
    the tab, and an empty tab means genuinely nothing happened.
    """
    annotations, prefetch = _feed_annotations(user)
    queryset = Post.objects.filter(is_deleted=False, created_at__gte=_window_start())
    queryset = queryset.select_related("author__candidate_profile")
    if prefetch is not None:
        queryset = queryset.prefetch_related(prefetch)
    return queryset.annotate(
        **annotations, activity=Count("votes", distinct=True) + Count("comments", distinct=True)
    ).order_by("-is_pinned", "-activity", "-created_at")


def comment_page(post: Post, page_size: int, offset: int) -> dict:
    """One page of top-level comments with replies nested in memory (04 §39).

    5.1 R3 pinned `Comment.Meta.ordering = ["created_at"]` so this pagination
    is stable. Reply authors come from a single secondary query for the page's
    replies — never one per comment.
    """
    top_level = (
        Comment.objects.filter(post=post, parent=None)
        .select_related("author__candidate_profile")
        .order_by("created_at")
    )
    total = top_level.count()
    page = list(top_level[offset : offset + page_size])
    replies = (
        Comment.objects.filter(parent__in=[c.id for c in page])
        .select_related("author__candidate_profile")
        .order_by("created_at")
        if page
        else Comment.objects.none()
    )
    by_parent: dict = {}
    for reply in replies:
        by_parent.setdefault(reply.parent_id, []).append(reply)
    return {"comments": page, "replies_by_parent": by_parent, "total_top_level": total}


class DuplicateVoteError(Exception):
    """The unique constraint rejected a repeat vote."""


def vote_post(user, post: Post) -> None:
    """Add the user's vote; a duplicate is the database's verdict (5.1 P3).

    The view translates `IntegrityError` into 409 `already_voted` — the DB
    constraint stays the real guarantee, the API just stops it becoming a 500.
    The insert runs inside a savepoint (`atomic()`): a rejected INSERT poisons
    the surrounding transaction in PostgreSQL, and without the savepoint the
    409 response itself would die on `TransactionManagementError`.
    """
    from django.db import transaction

    try:
        with transaction.atomic():
            post.votes.create(user=user)
    except IntegrityError as exc:
        raise DuplicateVoteError from exc


def unvote_post(user, post: Post) -> bool:
    """Remove the user's vote; returns whether a vote existed."""
    deleted, _ = post.votes.filter(user=user).delete()
    return deleted > 0
