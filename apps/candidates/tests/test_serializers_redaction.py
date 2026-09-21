"""Serializer redaction tests (T3.6/T3.8 core; 06 §5.2/§5.3): both public
serializers are pinned to the zero-exposure set over maximally-populated data."""

import pytest

from apps.accounts.models import User
from apps.candidates.models import get_public_display_name
from apps.candidates.serializers import AuthorPublicSerializer, CandidatePublicSerializer

pytestmark = pytest.mark.django_db

FORBIDDEN_KEYS = {
    "email",
    "phone",
    "fcm_token",
    "password",
    "notes",
    "moderation_state",
    "user",
    "interview_center",
    "interview_date",
    "offer_letter_date",
    "expected_joining_date",
    "joining_location",
    "created_at",
    "updated_at",
    "public_identity_mode",
}


@pytest.fixture
def maximal_user(verified_user):
    verified_user.email = "secret@tcs-internal.com"
    verified_user.save()
    return verified_user


def _maximal_profile(user, make_profile):
    return make_profile(
        user=user,
        display_name="Sai",
        public_identity_mode="DISPLAY_NAME",
        interview_center="Hyderabad",
        interview_date="2026-04-23",
        joining_location="Bengaluru",
        offer_letter_date="2026-05-05",
        expected_joining_date="2026-07-01",
    )


class TestCandidatePublicRedaction:
    def test_public_serializer_keys_minimal(self, maximal_user, make_profile):
        profile = _maximal_profile(maximal_user, make_profile)
        data = CandidatePublicSerializer(profile).data
        assert FORBIDDEN_KEYS.isdisjoint(data.keys())
        assert set(data.keys()) == {
            "id",
            "display_name",
            "batch",
            "hiring_type",
            "region",
            "current_status",
        }
        assert "secret@tcs-internal.com" not in str(data)

    def test_serialized_body_never_contains_email(self, maximal_user, make_profile):
        profile = _maximal_profile(maximal_user, make_profile)
        body = str(CandidatePublicSerializer(profile).data)
        assert "secret@tcs-internal.com" not in body
        assert "Hyderabad" not in body  # interview_center is owner-only


class TestAuthorPublicRedaction:
    def test_author_keys_and_no_pii(self, maximal_user, make_profile):
        _maximal_profile(maximal_user, make_profile)
        data = AuthorPublicSerializer(maximal_user).data
        assert FORBIDDEN_KEYS.isdisjoint(data.keys())
        assert set(data.keys()) == {"id", "display_name", "batch", "hiring_type", "region"}
        assert "secret@tcs-internal.com" not in str(data)
        assert data["display_name"] == "Sai"
        assert data["batch"] == "2025"

    def test_profileless_user_renders_anonymous_without_crash(self, verified_user):
        data = AuthorPublicSerializer(verified_user).data
        assert data["display_name"] == "Anonymous Candidate"
        assert data["batch"] is None
        assert data["hiring_type"] is None
        assert data["region"] is None

    def test_tombstoned_user_renders_anonymous_and_email_absent(self, make_profile):
        user = User.objects.create_user(
            "victim@example.com", "Correct Horse Battery 9!", is_verified=True
        )
        _maximal_profile(user, make_profile)
        user.email = "deleted_abc123@tracker.internal"
        user.is_active = False
        user.is_verified = False
        user.save()
        data = AuthorPublicSerializer(user).data
        assert "victim@example.com" not in str(data)
        assert data["display_name"] == "Sai"  # profile still exists (tombstone seam)

    def test_resolved_name_matches_resolver_in_all_five_cases(self, verified_user, make_profile):
        # 1) no profile
        assert AuthorPublicSerializer(verified_user).data["display_name"] == "Anonymous Candidate"
        # 2) ANONYMOUS mode
        profile = make_profile(user=verified_user, display_name="Sai")
        assert AuthorPublicSerializer(verified_user).data["display_name"] == "Anonymous Candidate"
        # 3) DISPLAY_NAME with value
        profile.public_identity_mode = "DISPLAY_NAME"
        profile.save()
        assert AuthorPublicSerializer(verified_user).data["display_name"] == "Sai"
        # 4) blank display_name
        profile.display_name = ""
        profile.save()
        assert AuthorPublicSerializer(verified_user).data["display_name"] == "Anonymous Candidate"
        # 5) whitespace-only display_name
        profile.display_name = "   "
        profile.save()
        expected = get_public_display_name(profile)
        assert AuthorPublicSerializer(verified_user).data["display_name"] == expected
        assert expected == "Anonymous Candidate"
