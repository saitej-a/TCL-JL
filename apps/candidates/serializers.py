"""Profile serializers (T3.4-T3.6; 3.2 D1-D4, 06 §5.1-§5.2).

Strict boundary segregation: ``CandidatePrivateSerializer`` serves only the
profile owner on ``/api/v1/profile/``; ``CandidatePublicSerializer`` and
``AuthorPublicSerializer`` are the ONLY community-facing shapes (Phase 5 feeds
import them) and are pinned by redaction tests to the 06 §5.3 zero-exposure set
(email, phone, FCM token, password, private notes, moderation state).
"""

from django.conf import settings
from rest_framework import serializers

from apps.accounts.models import User
from apps.candidates.models import (
    CandidateProfile,
    get_public_display_name,
    resolve_public_display_name,
)
from apps.candidates.validators import validate_batch_year


def validate_display_name(value: str) -> str:
    """T3.7 impersonation blocker (3.2 D3): case-insensitive substring match.

    Reads ``settings.RESERVED_DISPLAY_NAME_TOKENS`` at call time so additions
    apply without a deploy. Validation is mode-independent: a reserved name
    cannot be parked in ANONYMOUS mode and flipped on later.
    """
    cleaned = (value or "").strip()
    haystack = cleaned.casefold()
    for token in getattr(settings, "RESERVED_DISPLAY_NAME_TOKENS", []):
        if str(token).casefold() in haystack:
            raise serializers.ValidationError(
                "This display name is not allowed.",
                code="reserved_display_name",
            )
    return cleaned


class CandidatePrivateSerializer(serializers.ModelSerializer):
    """Owner representation — exact 04 §19 shape on /api/v1/profile/."""

    class Meta:
        model = CandidateProfile
        fields = [
            "id",
            "display_name",
            "public_identity_mode",
            "batch",
            "hiring_type",
            "region",
            "interview_center",
            "interview_date",
            "joining_location",
            "current_status",
            "offer_letter_date",
            "expected_joining_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    # Writable-but-controlled: accepted in PATCH bodies (04 §21 example), yet
    # never saved directly — the view hands it to update_profile(), which
    # routes it through transition_status. Invalid values fail DRF choice
    # validation here; illegal-but-valid values fail the state machine 400.
    current_status = serializers.ChoiceField(
        choices=CandidateProfile.Status.choices, required=False
    )

    def validate_display_name(self, value: str) -> str:
        return validate_display_name(value)

    def validate_batch(self, value: str) -> str:
        validate_batch_year(value)
        return value


class CandidateProfileCreateSerializer(serializers.ModelSerializer):
    """04 §20 create body — minus ``current_status`` (3.2 D1 side-channel: the
    view passes a requested status through the transition chain atomically)."""

    class Meta:
        model = CandidateProfile
        fields = [
            "display_name",
            "public_identity_mode",
            "batch",
            "hiring_type",
            "region",
            "interview_center",
            "interview_date",
            "joining_location",
            "offer_letter_date",
            "expected_joining_date",
        ]

    def validate_display_name(self, value: str) -> str:
        return validate_display_name(value)

    def validate_batch(self, value: str) -> str:
        validate_batch_year(value)
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if not (user.is_active and user.is_verified):
            raise serializers.ValidationError(
                {"user": ["Only active users with a verified email may create a profile."]},
                code="user_not_eligible",
            )
        # Duplicate detection lives in the view (deterministic 409 envelope);
        # create_profile still catches the IntegrityError race as 409.
        return attrs


class CandidatePublicSerializer(serializers.ModelSerializer):
    """Profile-sourced public shape — exactly 04 §23; nothing else renders."""

    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        fields = ["id", "display_name", "batch", "hiring_type", "region", "current_status"]

    def get_display_name(self, obj) -> str:
        return get_public_display_name(obj)


class AuthorPublicSerializer(serializers.ModelSerializer):
    """User-sourced community author representation (06 §5.1/§5.2).

    Defined in the profile domain so Phase 5 forum serializers import this
    exact redaction boundary instead of re-deriving it. None-safe sources:
    a profile-less user renders ``Anonymous Candidate`` with null cohort fields,
    never a crash, never an email.
    """

    display_name = serializers.SerializerMethodField()
    batch = serializers.CharField(source="candidate_profile.batch", read_only=True, default=None)
    hiring_type = serializers.CharField(
        source="candidate_profile.hiring_type", read_only=True, default=None
    )
    region = serializers.CharField(source="candidate_profile.region", read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "display_name", "batch", "hiring_type", "region"]

    def get_display_name(self, obj) -> str:
        return resolve_public_display_name(obj)
