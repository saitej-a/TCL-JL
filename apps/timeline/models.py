"""TimelineEvent (T4.1) — personal recruitment milestone events (03 §7).

The timeline is event-sourced rather than fixed date columns (03 §7 intro) so
milestones stay extensible. `is_verified` is admin-controlled moderation state
(Phase 8 tooling); candidate submissions always start unverified.

Status synchronization (TIME-02) lives in services.py — this module never writes
`current_status` directly.
"""

import uuid

from django.db import models

from apps.candidates.models import CandidateProfile


class TimelineEvent(models.Model):
    """A dated recruitment milestone belonging to exactly one candidate."""

    class EventType(models.TextChoices):
        INTERVIEW = "INTERVIEW", "Interview"
        SELECTION = "SELECTION", "Selection"
        OFFER_LETTER = "OFFER_LETTER", "Offer Letter"
        READINESS_SURVEY = "READINESS_SURVEY", "Readiness Survey"
        JOINING_LETTER = "JOINING_LETTER", "Joining Letter"
        JOINING_DATE = "JOINING_DATE", "Joining Date"
        JOINED = "JOINED", "Joined"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # CASCADE: account deletion removes private timeline events (06 §4.2 step 4).
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="timeline_events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    event_date = models.DateField()
    description = models.TextField(blank=True, default="")
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "timeline event"
        verbose_name_plural = "timeline events"
        ordering = ["-event_date", "-created_at"]
        indexes = [
            # T4.2: fast personal timeline rendering (newest first).
            models.Index(fields=["candidate", "-event_date"], name="idx_event_candidate_date"),
            # T4.2: analytics aggregation by milestone type over time (Phase 7).
            models.Index(fields=["event_type", "event_date"], name="idx_event_type_date"),
        ]

    def __str__(self) -> str:
        return f"{self.candidate} · {self.event_type} @ {self.event_date}"
