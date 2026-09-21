"""CandidateProfile model tests (T3.1/T3.3; 3.1 D3/D4)."""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from apps.accounts.models import User
from apps.candidates.models import (
    CandidateProfile,
    get_public_display_name,
    resolve_public_display_name,
)
from apps.candidates.validators import validate_batch_year

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "Correct Horse Battery 9!"


def _make_user(email="profile@test.dev", **extra):
    return User.objects.create_user(email, VALID_PASSWORD, **extra)


def _make_profile(user=None, **overrides) -> CandidateProfile:
    if user is None:
        user = _make_user()
    defaults = dict(user=user, batch="2025", hiring_type="DIGITAL", region="Hyderabad")
    defaults.update(overrides)
    return CandidateProfile.objects.create(**defaults)


class TestCreationDefaults:
    def test_defaults_registered_anonymous_blank_name(self):
        profile = _make_profile()
        assert profile.current_status == CandidateProfile.Status.REGISTERED
        assert profile.public_identity_mode == CandidateProfile.PublicIdentityMode.ANONYMOUS
        assert profile.display_name == ""
        assert profile.get_public_display_name() == "Anonymous Candidate"

    def test_hiring_type_choices_enforced(self):
        profile = _make_profile(hiring_type="CONTRACTOR")
        with pytest.raises(ValidationError):
            profile.full_clean(exclude=["user"])

    def test_uuid_primary_key(self):
        profile = _make_profile()
        uuid.UUID(str(profile.id))  # raises if not UUID


class TestNullableOneToOne:
    def test_user_without_profile_has_no_candidate_profile(self):
        user = _make_user("noprofile@test.dev")
        assert not CandidateProfile.objects.filter(user=user).exists()
        assert getattr(user, "candidate_profile", None) is None
        assert resolve_public_display_name(user) == "Anonymous Candidate"

    def test_second_profile_for_same_user_impossible(self):
        user = _make_user("dup@test.dev")
        _make_profile(user)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _make_profile(user)

    def test_tombstoned_user_simply_has_no_profile(self):
        user = _make_user("tomb@test.dev")
        user.email = "deleted_abc@tracker.internal"
        user.is_active = False
        user.is_verified = False
        user.save()
        assert not CandidateProfile.objects.filter(user=user).exists()


class TestPublicDisplayName:
    def test_missing_profile_anonymous(self):
        user = _make_user()
        assert get_public_display_name(None) == "Anonymous Candidate"
        assert resolve_public_display_name(user) == "Anonymous Candidate"

    def test_anonymous_mode_hides_display_name(self):
        profile = _make_profile(display_name="Sai T.", public_identity_mode="ANONYMOUS")
        assert profile.get_public_display_name() == "Anonymous Candidate"

    def test_display_name_mode_shows_name(self):
        profile = _make_profile(display_name="Sai T.", public_identity_mode="DISPLAY_NAME")
        assert profile.get_public_display_name() == "Sai T."

    def test_blank_display_name_falls_back_to_anonymous(self):
        profile = _make_profile(display_name="", public_identity_mode="DISPLAY_NAME")
        assert profile.get_public_display_name() == "Anonymous Candidate"

    def test_whitespace_display_name_falls_back_to_anonymous(self):
        profile = _make_profile(display_name="   ", public_identity_mode="DISPLAY_NAME")
        assert profile.get_public_display_name() == "Anonymous Candidate"

    def test_email_never_in_public_output(self):
        user = _make_user("secretive@test.dev")
        _make_profile(user=user, display_name="Secretive", public_identity_mode="DISPLAY_NAME")
        assert "secretive@test.dev" not in resolve_public_display_name(user)


class TestBatchValidator:
    def test_accepts_offered_year(self):
        validate_batch_year("2025")  # no raise

    def test_rejects_unoffered_year(self):
        with pytest.raises(ValidationError) as exc:
            validate_batch_year("2027")
        assert exc.value.code == "batch_not_offered"

    def test_settings_extension_revalidates_without_migration(self):
        """D3: adding 2027 is a settings change, not a schema change."""
        with override_settings(BATCH_YEARS=["2024", "2025", "2026", "2027"]):
            validate_batch_year("2027")  # no raise now
        with pytest.raises(ValidationError):
            validate_batch_year("2027")  # back to baseline settings

    def test_model_save_rejects_unoffered_batch(self):
        profile = _make_profile(batch="1999")
        with pytest.raises(ValidationError):
            profile.full_clean(exclude=["user"])


class TestMetaIndexes:
    def test_single_column_indexes_present(self):
        names = {idx.name for idx in CandidateProfile._meta.indexes}
        expected = {
            "idx_profile_batch",
            "idx_profile_hiring_type",
            "idx_profile_region",
            "idx_profile_status",
            "idx_profile_join_loc",
            "idx_profile_interview_dt",
            "idx_profile_offer_dt",
            "idx_profile_joining_dt",
        }
        assert expected <= names
