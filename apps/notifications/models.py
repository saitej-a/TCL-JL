"""Notification / device models — the delivery substrate for Phase 6 (T6.1-T6.3; 6.1 D1-D6).

Domain shape (07 §3.1-§3.3, 03 §8 + §12):

* `Notification` — the authoritative, append-only log of in-app alerts. `title` and
  `message` are **stored snapshots** written at creation time (D3): deleting the
  source post or comment later must not rewrite what a user was told, so this model
  composes and renders nothing (D4). Anonymity-safe labels ("A candidate", a handle)
  are baked in by 6.2's `create_notification` service via `AuthorPublicSerializer`
  semantics, which is what makes 07 §8's zero-PII push rule achievable at write time
  instead of patched per reader.
* `Device` — FCM registration tokens, kept off the `User` model so one account can
  hold several browsers/phones (03 §8). 03 §8: "FCM tokens are sensitive
  infrastructure identifiers. Never expose them through public APIs" — this module
  therefore ships no token-rendering surface at all, and `write_only = True` on
  6.2's registration serializer is that rule's binding contract.
* `NotificationPreference` — the per-candidate push controls (07 §3.3), created
  lazily and explicitly via `get_or_create_for` (R6) — no `post_save` signal, so
  nothing has to be registered at import time and a new user really starts with no
  row.

Integrity guarantee (D5, beyond 07 §3.1's schema): `notification_read_state` — a
database-level `CheckConstraint` refusing a notification that claims to be read
without a read timestamp. It is the project's first `CheckConstraint`, so both layers
are proven separately: PostgreSQL holds the invariant no matter who writes (ORM,
`QuerySet.update`, admin, bulk ops; `clean()` does **not** run on those paths), and
`clean()` is the application mirror carrying the stable code
`read_state_inconsistent` for request-time callers. `mark_as_read()` (R4) is the
single sanctioned writer of the `is_read`/`read_at` pair. The constraint is
deliberately one-directional — `read_at` set while `is_read` is still False is legal,
because the timestamp and the flag can legitimately arrive in that order.

Deliberate, documented deviations (recorded for the verification record):

* **R1** — 07 §3.1-§3.2 declare the compound indexes with no names and add
  field-level `db_index=True` on individual columns. The compounds get repo-style
  names (4.1 / 5.1 P3); the field-level flags are kept **literally**, even though the
  single-column indexes on `recipient` and `user` are redundant with the leading
  column of the compounds. Dropping them would be silent spec drift, and at MVP scale
  the extra index costs nothing.
* **R3** — `Device.__str__` renders device type + browser, not `self.user.email` as
  07 §3.2 writes it. `__str__` reaches logs, admin lists, and error reports, and
   03 §8 already classes what sits behind a token as sensitive.
* **R9** — `last_seen_at` and `updated_at` are both `auto_now` (the spec has both).
  With `save(update_fields=[...])` an `auto_now` field is only refreshed when it is
  named in `update_fields`, so 6.2's token-refresh path must list `last_seen_at`
  explicitly when it wants the refresh timestamp moved.

Out of scope here: no serializer, view, URL, permission, task, or admin registration —
6.2 (endpoints) and 6.3 (Celery/FCM) own those.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# The `clean()` mirror's error code (D5). A module constant because 6.2 asserts on
# it when it translates application validation into an HTTP 400.
READ_STATE_INCONSISTENT = "read_state_inconsistent"
_READ_STATE_MESSAGE = "A notification marked as read must carry a read timestamp."


class NotificationManager(models.Manager):
    """Manager for the notification log (D6)."""

    def unread_count_for(self, user) -> int:
        """Count `user`'s unread notifications (4.2 D1's promised seam).

        4.2 shipped `community.unread_notifications: 0` as an explicit placeholder
        and named Phase 6 as its author; this is that helper, and 6.2 performs the
        wiring. The filter walks the `(recipient, is_read)` prefix of
        `idx_notif_recip_read_created` (R-5), and there is deliberately **no**
        `order_by()` — ordering would turn an index-only count into a sort.
        """
        return self.filter(recipient=user, is_read=False).count()


class Notification(models.Model):
    """One stored in-app alert for one recipient (07 §3.1, 03 §12)."""

    class NotificationType(models.TextChoices):
        """The closed, system-owned event vocabulary (D1/D2).

        All seven of 07 §3.1's values ship now, not just the four with v1 producers
        (COMMENT, REPLY, VOTE_MILESTONE, ANNOUNCEMENT): `MODERATION` is Phase 8's and
        `TIMELINE_REMINDER`/`SYSTEM` are reused as-is, so extending coverage needs no
        migration. `10_MVP_TASKS.md` T6.1 lists six and omits `SYSTEM` — the spec is
        authoritative. A `TextChoices` enum rather than a settings-held list (unlike
        5.1 D1's `POST_CATEGORIES`) because these values drive code dispatch in
        6.2/6.3: a settings-added type would reach the dispatcher with no handler.
        """

        COMMENT = "COMMENT", "New Comment"
        REPLY = "REPLY", "New Reply"
        VOTE_MILESTONE = "VOTE_MILESTONE", "Upvote Milestone"
        ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
        MODERATION = "MODERATION", "Moderation Alert"
        TIMELINE_REMINDER = "TIMELINE_REMINDER", "Timeline Reminder"
        SYSTEM = "SYSTEM", "System Alert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
        db_index=True,
    )
    # Stored snapshots (D3) — never recomposed from the source content at read time.
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Explicit nullable FKs rather than a GenericForeignKey (03 §12). Nullable
    # because SYSTEM / TIMELINE_REMINDER / MODERATION notifications are legitimate
    # without community context. CASCADE is kept per 03 §19's relationship table but
    # is dormant by design (R8): 5.1 removes content by flag and 2.2 anonymizes users
    # rather than deleting rows, so no production path reaches a cascading delete.
    post = models.ForeignKey(
        "community.Post",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    comment = models.ForeignKey(
        "community.Comment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = NotificationManager()

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        # R7: pinned now, because 6.2's pagination must be stable and the ordering
        # has to match the compound indexes' shape before the endpoints are written.
        ordering = ["-created_at"]
        indexes = [
            # Unread list + D6's count: the (recipient, is_read) prefix serves both.
            # The name is abbreviated because Django refuses index names longer than
            # 30 characters (models.E034) — R1's longer spelling does not fit.
            models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="idx_notif_recip_read_created",
            ),
            # The full inbox / history read path for 6.2's list endpoint.
            models.Index(
                fields=["recipient", "-created_at"],
                name="idx_notif_recipient_created",
            ),
        ]
        constraints = [
            # D5 — the phase's hard guarantee, proven at the DB layer in
            # tests/test_read_state_constraint.py. `condition=`, not the deprecated
            # `check=` (R2, RemovedInDjango60Warning on the pinned Django 5.2).
            models.CheckConstraint(
                condition=models.Q(is_read=False) | models.Q(read_at__isnull=False),
                name="notification_read_state",
            )
        ]

    def clean(self):
        """Application mirror of `notification_read_state` (D5).

        Exactly one combination is inconsistent — read without a timestamp. The
        mirror exists so a request-time caller gets a `ValidationError` with a stable
        code instead of a raw `IntegrityError` surfaced from the driver.
        """
        if self.is_read and self.read_at is None:
            # A nested `ValidationError` (not a plain string) so the detail keeps its
            # machine-readable code, mirroring how `Post.clean()` extends
            # `error_list` rather than flattening to messages.
            raise ValidationError(
                {"read_at": [ValidationError(_READ_STATE_MESSAGE, code=READ_STATE_INCONSISTENT)]}
            )

    def mark_as_read(self) -> bool:
        """The sanctioned writer of the `is_read`/`read_at` pair (R4).

        Writes both fields in one `UPDATE` so the pair can never disagree
        mid-transaction, and returns whether *this* call flipped the row, so 6.2 can
        report "already read" honestly instead of guessing.
        """
        if self.is_read:
            return False
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])
        return True


class Device(models.Model):
    """A registered browser or mobile endpoint holding an FCM token (07 §3.2, 03 §8)."""

    class DeviceType(models.TextChoices):
        """Web/Android/iOS/other — 07 §3.2's vocabulary verbatim.

        `10_MVP_TASKS.md` T6.2 lists three and omits `OTHER`; the spec is
        authoritative.
        """

        WEB = "WEB", "Web Browser"
        ANDROID = "ANDROID", "Android Web/PWA"
        IOS = "IOS", "iOS Web/PWA"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices",
        db_index=True,
    )
    # Unbounded Text rather than CharField because FCM tokens are long and opaque;
    # unique=True is what lets 6.2's registration path upsert by token instead of
    # creating a duplicate row (R-3 notes the btree-index size cap is a non-issue
    # for ~150-250 char tokens at MVP scale).
    fcm_token = models.TextField(unique=True, help_text="Firebase registration token")
    device_type = models.CharField(
        max_length=16,
        choices=DeviceType.choices,
        default=DeviceType.WEB,
    )
    browser = models.CharField(max_length=64, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    # R9: both auto_now — see the module docstring for the `update_fields` caveat.
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "device"
        verbose_name_plural = "devices"
        ordering = ["-last_seen_at"]  # R7 — 6.2's device list reads newest-first.
        indexes = [
            models.Index(fields=["user", "is_active"], name="idx_device_user_active"),
        ]

    def __str__(self) -> str:
        """No PII, no token (R3, T-6.1-01).

        Deliberate micro-deviation from 07 §3.2, which renders `self.user.email`:
        server-side `__str__` reaches logs, admin list displays, and error reports,
        and 03 §8 already declares what sits behind a token to be sensitive.
        """
        return f"{self.get_device_type_display()} ({self.browser or 'unknown browser'})"


class NotificationPreference(models.Model):
    """Per-candidate push controls; one row per user, created lazily (07 §3.3, R6)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    notify_on_comment = models.BooleanField(
        default=True, help_text="Notify when someone comments on your post"
    )
    notify_on_reply = models.BooleanField(
        default=True, help_text="Notify when someone replies to your comment"
    )
    notify_on_vote_milestone = models.BooleanField(
        default=True, help_text="Notify on post upvote milestones"
    )
    notify_on_announcements = models.BooleanField(
        default=True, help_text="Notify on admin community announcements"
    )
    notify_timeline_reminders = models.BooleanField(
        default=True, help_text="Periodic reminders to update timeline"
    )
    push_enabled = models.BooleanField(
        default=True, help_text="Global master toggle for browser push"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "notification preference"
        verbose_name_plural = "notification preferences"

    @classmethod
    def get_or_create_for(cls, user):
        """The single accessor for a user's preferences (R6).

        Lazily created and explicit: no `post_save` signal ships, because import-time
        signal registration is a test-ordering hazard and would silently write a row
        for every user ever created. Returns `(preference, created)` like
        `QuerySet.get_or_create`, so 6.2 can tell a first-time reader from a
        repeat one.
        """
        return cls.objects.get_or_create(user=user)
