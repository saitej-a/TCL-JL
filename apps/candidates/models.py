"""CandidateProfile (T3.1) — 1:1 recruitment identity, separate from auth (03 §5).

Public display resolution (T3.3) is deliberately safe for users without a
profile (3.1 D4): community code must never crash or leak email because a
candidate hasn't onboarded yet.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.candidates.validators import validate_batch_year


def resolve_public_display_name(user) -> str:
    """T3.3 module-level resolver: anonymous label whenever identity is absent
    or hidden. Never includes email (03 §5)."""
    profile = getattr(user, "candidate_profile", None)
    return get_public_display_name(profile)


def get_public_display_name(profile: "CandidateProfile | None") -> str:
    if profile is None:
        return "Anonymous Candidate"
    if profile.public_identity_mode == CandidateProfile.PublicIdentityMode.ANONYMOUS:
        return "Anonymous Candidate"
    cleaned = (profile.display_name or "").strip()
    return cleaned if cleaned else "Anonymous Candidate"


class CandidateProfile(models.Model):
    """Recruitment details for a candidate. Auth stays on accounts.User."""

    class PublicIdentityMode(models.TextChoices):
        ANONYMOUS = "ANONYMOUS", "Anonymous"
        DISPLAY_NAME = "DISPLAY_NAME", "Display Name"

    class HiringType(models.TextChoices):
        PRIME = "PRIME", "Prime"
        DIGITAL = "DIGITAL", "Digital"
        NINJA = "NINJA", "Ninja"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        INTERVIEWED = "INTERVIEWED", "Interviewed"
        SELECTED = "SELECTED", "Selected"
        OFFER_RECEIVED = "OFFER_RECEIVED", "Offer Received"
        READINESS_SURVEY = "READINESS_SURVEY", "Readiness Survey"
        WAITING_FOR_JOINING_LETTER = "WAITING_FOR_JOINING_LETTER", "Waiting for Joining Letter"
        JOINING_LETTER_RECEIVED = "JOINING_LETTER_RECEIVED", "Joining Letter Received"
        JOINING_DATE_RECEIVED = "JOINING_DATE_RECEIVED", "Joining Date Received"
        JOINED = "JOINED", "Joined"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"  # terminal (3.1 D1)
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # D4: nullable 1:1, no auto-create signals; SET_NULL is belt-and-braces —
    # the 2.2 deletion service anonymizes User rows rather than deleting them.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="candidate_profile",
    )
    display_name = models.CharField(max_length=50, blank=True, default="")
    public_identity_mode = models.CharField(
        max_length=12,
        choices=PublicIdentityMode.choices,
        default=PublicIdentityMode.ANONYMOUS,
    )
    batch = models.CharField(max_length=10, validators=[validate_batch_year])
    hiring_type = models.CharField(max_length=10, choices=HiringType.choices)
    region = models.CharField(max_length=100)  # free text (3.1 D3)
    interview_center = models.CharField(max_length=200, blank=True, default="")
    interview_date = models.DateField(null=True, blank=True)
    joining_location = models.CharField(max_length=200, blank=True, default="")
    current_status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.REGISTERED,
    )
    offer_letter_date = models.DateField(null=True, blank=True)
    expected_joining_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "candidate profile"
        verbose_name_plural = "candidate profiles"
        indexes = [
            models.Index(fields=["batch"], name="idx_profile_batch"),
            models.Index(fields=["hiring_type"], name="idx_profile_hiring_type"),
            models.Index(fields=["region"], name="idx_profile_region"),
            models.Index(fields=["current_status"], name="idx_profile_status"),
            models.Index(fields=["joining_location"], name="idx_profile_join_loc"),
            models.Index(fields=["interview_date"], name="idx_profile_interview_dt"),
            models.Index(fields=["offer_letter_date"], name="idx_profile_offer_dt"),
            models.Index(fields=["expected_joining_date"], name="idx_profile_joining_dt"),
        ]

    def __str__(self) -> str:
        return f"{self.get_public_display_name()} ({self.batch} · {self.hiring_type})"

    def get_public_display_name(self) -> str:
        return get_public_display_name(self)
