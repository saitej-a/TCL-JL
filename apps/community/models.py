"""Community models — Post, Comment, PostVote (T5.1-T5.3; 5.1 D1-D4, P1-P4).

Domain shape (03 §9-§11):

* `Post` — a categorized discussion thread. Counters are **not** stored: votes and
  comments are aggregated at read time (03 §9, §29, §30) so they can never drift.
* `Comment` — a thread comment with a nullable self-FK giving strict 1-level
  replies. `parent` is `SET_NULL` rather than `CASCADE` so a hard delete can never
  destroy a sub-thread's content; soft delete is the only removal path this
  project uses anyway.
* `PostVote` — one row per `(user, post)`, enforced by the database.

Author policy (D2): `author` is required and uses `PROTECT`. Account deletion in
this project anonymizes the User row rather than removing it (2.2), and 3.2's
`AuthorPublicSerializer` already renders that anonymized row as anonymous with no
email — so the retained row *is* the tombstone and nothing downstream needs a
NULL-author branch. `PROTECT` makes that assumption enforced rather than assumed.

Integrity guarantees are deliberately unequal, and the difference is honest:

* **Duplicate votes are impossible at the database level** (`unique_user_post_vote`)
  — the invariant never depends on application code.
* **Reply depth is application-level.** "A reply may not be a reply's parent" is a
  cross-row rule (`parent.parent IS NOT NULL`), which PostgreSQL cannot express as
  a `CHECK`, and Django has no equivalent constraint. It is enforced by
  `validators.validate_reply_depth` on the write path (services) and mirrored in
  `clean()` for admin/forms — see that module for the codes.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.community.validators import (
    validate_not_blank,
    validate_post_category,
    validate_reply_depth,
    validate_title_length,
)


class Post(models.Model):
    """A community discussion thread (03 §9, T5.1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PROTECT: community authorship is never silently destroyed (5.1 D2).
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="community_posts",
    )
    title = models.CharField(max_length=200, validators=[validate_not_blank, validate_title_length])
    body = models.TextField(validators=[validate_not_blank])
    # No `choices`: the vocabulary is settings-driven so extending it never needs a
    # migration (5.1 D1). `validate_post_category` reads the setting at call time.
    category = models.CharField(max_length=20, validators=[validate_post_category])
    is_pinned = models.BooleanField(default=False)  # moderator control (Phase 8)
    is_locked = models.BooleanField(default=False)  # disables new comments (COMM-06)
    is_deleted = models.BooleanField(default=False)  # soft delete (COMM-05, 03 §20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "post"
        verbose_name_plural = "posts"
        # Pinned threads first, then newest — 03 §17's (is_pinned, created_at) index
        # is built for this order, and 5.2's pagination depends on it being stable.
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["category", "created_at"], name="idx_post_category_created"),
            models.Index(fields=["created_at"], name="idx_post_created"),
            models.Index(fields=["is_pinned", "created_at"], name="idx_post_pinned_created"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.category})"

    def clean(self):
        """Admin/form path — the services run the same validators on the API path."""
        errors = {}
        for field, validator in (
            ("title", validate_not_blank),
            ("title", validate_title_length),
            ("body", validate_not_blank),
            ("category", validate_post_category),
        ):
            try:
                validator(getattr(self, field))
            except ValidationError as exc:
                # `error_list`, not `messages`: it keeps each ErrorDetail's code, so
                # the admin/form path raises the same machine-readable codes
                # (`invalid_category`, `title_too_long`, ...) as the services.
                errors.setdefault(field, []).extend(exc.error_list)
        if errors:
            raise ValidationError(errors)


class Comment(models.Model):
    """A post comment, optionally a reply to a top-level comment (03 §10, T5.2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="community_comments",
    )
    # SET_NULL, not CASCADE (5.1 P1): if a parent ever disappears, its replies are
    # promoted to top-level rather than deleted with it.
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    body = models.TextField(validators=[validate_not_blank])
    is_deleted = models.BooleanField(default=False)  # soft delete (COMM-05, 03 §20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "comment"
        verbose_name_plural = "comments"
        ordering = ["created_at"]  # conversation order (03 §17: (post, created_at))
        indexes = [
            models.Index(fields=["post", "created_at"], name="idx_comment_post_created"),
            models.Index(fields=["parent", "created_at"], name="idx_comment_parent_created"),
        ]

    def __str__(self) -> str:
        return f"Comment on {self.post_id} by {self.author_id}"

    def clean(self):
        errors = {}
        try:
            validate_not_blank(self.body)
        except ValidationError as exc:
            errors.setdefault("body", []).extend(exc.error_list)
        try:
            validate_reply_depth(self)
        except ValidationError as exc:
            errors.setdefault("parent", []).extend(exc.error_list)
        if errors:
            raise ValidationError(errors)


class PostVote(models.Model):
    """A single upvote of a post (03 §11, T5.3).

    `unique_user_post_vote` is the phase's hard guarantee: a duplicate vote is
    rejected by PostgreSQL, not by a serializer (roadmap success criterion 3).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_votes",
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "post vote"
        verbose_name_plural = "post votes"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_user_post_vote",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} voted {self.post_id}"


class Announcement(models.Model):
    """A staff-authored community broadcast (Phase 8.2 — T8.6/T8.10; 08 §7.1).

    Lifecycle (§7): draft → ``publish()`` sets `is_published` + `published_at` and
    dispatches the FCM broadcast → pinned rows render as a sticky top banner →
    ``expires_at`` lapses and the hourly ``clean_expired_announcements`` task
    unpublishes the row (no deletion — 04 §75 allows direct delete, but unpublish
    keeps the author's wording available for later review).

    `publish()` is the **single sanctioned trigger** for the broadcast (never a
    post_save signal — 6.1 R6's import-time-signal hazard) and it is idempotent:
    only the False→True transition dispatches, so re-saving a published row is a
    no-op for the fan-out.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_published = models.BooleanField(default=False, db_index=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "announcement"
        verbose_name_plural = "announcements"
        ordering = ["-is_pinned", "-published_at"]
        indexes = [
            # §7.1's composite; name abbreviated to fit Django's 30-char limit.
            models.Index(
                fields=["is_published", "is_pinned", "-published_at"],
                name="idx_announce_pub_pin_pubat",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def publish(self) -> bool:
        """Publish + dispatch the broadcast. Returns True iff this call published.

        Idempotent by transition: an already-published row dispatches nothing
        (D7/T8.10 — one broadcast per publication).
        """
        from apps.community.tasks import broadcast_announcement_dispatch

        if self.is_published:
            return False
        self.is_published = True
        self.published_at = timezone.now()
        self.save(update_fields=["is_published", "published_at", "updated_at"])
        broadcast_announcement_dispatch(str(self.pk))
        return True
