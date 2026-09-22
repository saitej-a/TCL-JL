"""Moderation models (Phase 8.1 — MOD-01/MOD-02, 08_MODERATION.md §3.2).

The `Report` model implements 08 §3.2's schema with one recorded deviation:
`post`/`comment` use `on_delete=models.CASCADE` instead of §3.2's `SET_NULL`.

Rationale (08.1 RESEARCH §2): the XOR CheckConstraint requires exactly one of
(`post`, `comment`) to be non-null. With `SET_NULL`, hard-deleting a target
would UPDATE the surviving report row to (NULL, NULL) — re-validating the
constraint and raising IntegrityError at delete time. CASCADE keeps every
report row pointing at a live target; post hard-deletion stays unblocked
(5.1 D4: a disappearing post must never be blocked by its reports), and
moderator notes on dismissed/resolved reports remain the audit trail for
vanished targets. Pending-dedup is enforced twice: application check (services)
and two conditional UniqueConstraints at the database (race-safe, 5.1 P4).
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Report(models.Model):
    """A candidate's report against exactly one post or one comment."""

    class ReportReason(models.TextChoices):
        SPAM = "SPAM", "Spam or Commercial Promotion"
        HARASSMENT = "HARASSMENT", "Harassment or Abuse"
        MISINFORMATION = "MISINFORMATION", "False Information / Rumors"
        ABUSIVE_CONTENT = "ABUSIVE_CONTENT", "Profanity or Vulgarity"
        PERSONAL_INFORMATION = "PERSONAL_INFORMATION", "Private Personal Information"
        SCAM = "SCAM", "Fraud or Fee Solicitation"
        OTHER = "OTHER", "Other Violation"

    class ReportStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        REVIEWED = "REVIEWED", "Reviewed"
        RESOLVED = "RESOLVED", "Resolved (Action Taken)"
        DISMISSED = "DISMISSED", "Dismissed (No Violation)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_reports",
        db_index=True,
    )
    # Deviation from 08 §3.2: CASCADE, not SET_NULL — see module docstring.
    post = models.ForeignKey(
        "community.Post",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )
    comment = models.ForeignKey(
        "community.Comment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )
    reason = models.CharField(max_length=32, choices=ReportReason.choices, db_index=True)
    description = models.TextField(blank=True, max_length=1000)
    status = models.CharField(
        max_length=16, choices=ReportStatus.choices, default=ReportStatus.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_reports",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderator_notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="idx_report_status_created"),
            models.Index(fields=["post", "status"], name="idx_report_post_status"),
            models.Index(fields=["comment", "status"], name="idx_report_comment_status"),
        ]
        constraints = [
            # Exactly one target (08 §3.2): post XOR comment, never both, never neither.
            models.CheckConstraint(
                condition=(
                    models.Q(post__isnull=False, comment__isnull=True)
                    | models.Q(post__isnull=True, comment__isnull=False)
                ),
                name="report_exactly_one_target",
            ),
            # Pending dedup (08 §3.3 / 04 §66) at database law, race-safe:
            # one PENDING report per (reporter, post) and per (reporter, comment).
            models.UniqueConstraint(
                fields=["reporter", "post"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_report_per_post",
            ),
            models.UniqueConstraint(
                fields=["reporter", "comment"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_report_per_comment",
            ),
        ]

    def clean(self):
        """Application mirror of the XOR constraint (§3.2's clean, message verbatim)."""
        if bool(self.post) == bool(self.comment):
            raise ValidationError(
                "A report must target either a post or a comment, not both or neither."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        target = "POST" if self.post_id else "COMMENT" if self.comment_id else "?"
        return f"Report {self.pk} {self.reason} {target} {self.status}"
