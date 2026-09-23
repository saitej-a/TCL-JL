"""Community API serializers (T5.4-T5.11; 5.2 D1-D4, D5, P6, P9; 04 §31-§42).

Author identity is the security-sensitive surface here. Every author payload
comes from one place — `CommunityAuthorSerializer`, wrapping 3.2's
`AuthorPublicSerializer` redaction boundary plus the D2 `avatar_seed` — so no
endpoint can accidentally render an email, a real name, or a derivable colour.

D3 (recorded deviation from 08 §406): tombstoned content **keeps** its author
handle. The handle is anonymity-safe through `AuthorPublicSerializer`, so
removal hides the words, not the participation — verification reports this as
known, not as a bug.

Read shapes render through `tombstones.display_*` (5.1 R2) so the tombstone has
exactly one copy source. Write serializers own *shape* only; the invariants
belong to the 5.1 services, which the views call (the 3.1/3.2 split).
"""

import hmac
from hashlib import sha256

from django.conf import settings
from rest_framework import serializers

from apps.candidates.serializers import AuthorPublicSerializer
from apps.community.models import Announcement, Comment, Post
from apps.community.tombstones import display_body, display_title

# 05 §60's anonymous palette (10 colour buckets). Size is a UI concern; only
# the seed→index mapping lives server-side.
AVATAR_PALETTE_SIZE = 10


def avatar_seed(candidate_id) -> int:
    """Deterministic-but-uncomputable palette index (5.2 D2 / 05 §60).

    HMAC over the candidate id with a server-side secret: stable across
    requests (discussions stay followable) yet uncomputable by clients, so a
    colour cannot link a pseudonym across threads or survive a display-name
    change as a tracking vector. `candidate_id` may be None (profile-less
    author) — the seed is then constant, which is fine: it only colours.
    """
    secret = settings.AVATAR_SEED_SECRET.encode()
    digest = hmac.new(secret, str(candidate_id).encode(), sha256).digest()
    return int.from_bytes(digest[:4], "big") % AVATAR_PALETTE_SIZE


class CommunityAuthorSerializer(AuthorPublicSerializer):
    """The only author shape 5.2 renders: 3.2's redaction + `avatar_seed`."""

    avatar_seed = serializers.SerializerMethodField()

    class Meta(AuthorPublicSerializer.Meta):
        fields = AuthorPublicSerializer.Meta.fields + ["avatar_seed"]

    def get_avatar_seed(self, obj) -> int:
        profile = getattr(obj, "candidate_profile", None)
        return avatar_seed(profile.pk if profile is not None else None)


class PostCardSerializer(serializers.ModelSerializer):
    """Feed card (04 §31) — counts aggregated at read time, tombstone-masked.

    The view's queryset supplies `vote_count`/`comment_count` annotations with
    `distinct=True` — counting two reverse FKs without `distinct` multiplies
    rows (3 votes × 2 comments ⇒ 6/6), the exact trap COMM-08 would hide
    behind a passing no-N+1 check. `comment_count` includes tombstones (D4) so
    the card's number matches the thread the reader actually opens.
    """

    author = CommunityAuthorSerializer(read_only=True)
    vote_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    has_voted = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "body",
            "category",
            "is_pinned",
            "is_locked",
            "is_deleted",
            "vote_count",
            "comment_count",
            "has_voted",
            "created_at",
            "updated_at",
        ]

    def get_title(self, obj) -> str:
        return display_title(obj)

    def get_body(self, obj) -> str:
        return display_body(obj)

    def get_has_voted(self, obj) -> bool:
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        votes = getattr(obj, "user_votes", None)
        if votes is not None:
            return any(v.user_id == user.id for v in votes)
        # Fallback for un-annotated instances (create responses). One query
        # per card is acceptable there: the response holds exactly one post.
        return obj.votes.filter(user=user).exists()


class PostWriteSerializer(serializers.Serializer):
    """Create/edit body (04 §32, §37). Validation lives in the 5.1 services."""

    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    category = serializers.CharField(max_length=20)


class CommentSerializer(serializers.ModelSerializer):
    """Threaded comment (04 §39). `is_deleted` is exposed read-only so the UI
    can grey out tombstones (P9: tombstones stay in their threads)."""

    author = CommunityAuthorSerializer(read_only=True)
    # Rendered from the *_id columns: a PrimaryKeyRelatedField would fetch the
    # related Post/Parent row per comment — an N+1 COMM-08's budget would flag.
    post = serializers.UUIDField(source="post_id", read_only=True)
    parent = serializers.UUIDField(source="parent_id", read_only=True)
    body = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "parent",
            "author",
            "body",
            "is_deleted",
            "replies",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "post",
            "parent",
            "author",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    def get_body(self, obj) -> str:
        return display_body(obj)

    def get_replies(self, obj):
        # Preloaded by the view's `comment_page` (one query per page, COMM-08);
        # anything not preloaded (detail route) falls back to one query.
        if "replies" in getattr(obj, "_prefetched_objects_cache", {}):
            children = obj.replies.all()
        elif self.context.get("replies_by_parent"):
            children = self.context["replies_by_parent"].get(obj.id, [])
        else:
            children = obj.replies.select_related("author__candidate_profile").all()
        return CommentReplySerializer(children, many=True, context=self.context).data


class CommentReplySerializer(CommentSerializer):
    """One nesting level only — a reply never carries children (04 §40)."""

    def get_replies(self, obj):
        return []


class CommentWriteSerializer(serializers.Serializer):
    """Create body (04 §41). Rules beyond shape (locked post, deleted post,
    parent's post) are enforced in the view/service, not here."""

    body = serializers.CharField()
    parent_id = serializers.UUIDField(required=False, allow_null=True)


class AnnouncementPublicSerializer(serializers.ModelSerializer):
    """04 §72's public read shape.

    No `created_by` (staff identity is not community-visible) and no
    `is_published` — the public list only ever contains published rows, so
    echoing the flag would invite a client to filter on something the server
    already guarantees (Phase 8.2).
    """

    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "is_pinned", "published_at", "expires_at"]
        read_only_fields = fields


class AnnouncementWriteSerializer(serializers.ModelSerializer):
    """04 §73/§74's staff write shape.

    `is_published` is deliberately absent: publication is the `publish()`
    transition (which stamps `published_at` and dispatches the broadcast), not a
    general write. A PATCH may still carry `is_published=true` as the publish
    signal — the view routes that through `publish()` rather than saving it.
    """

    class Meta:
        model = Announcement
        fields = ["title", "body", "is_pinned", "expires_at"]


class VoteSerializer(serializers.ModelSerializer):
    """04 §43's single vote shape (T5.9). `vote_count` is declared explicitly:
    it's an annotation supplied by the view, not a model field."""

    vote_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = ["id", "vote_count", "is_pinned", "is_locked"]
        read_only_fields = fields
