"""``GET /me/`` tests (04 §18, 06 §5.2): exact shape, zero sensitive leakage."""

import pytest

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db

ME_URL = "/api/v1/me/"
VALID_PASSWORD = "Correct Horse Battery 9!"


@pytest.fixture
def user():
    return User.objects.create_user("me@example.com", VALID_PASSWORD, is_verified=True)


def _complete_profile(user: User) -> CandidateProfile:
    """A profile with every wizard field present (9.2 D1: completion = truthful)."""
    return CandidateProfile.objects.create(
        user=user,
        display_name="Me Candidate",
        batch="2025",
        hiring_type=CandidateProfile.HiringType.DIGITAL,
        region="Hyderabad",
        offer_letter_date="2025-03-15",
    )


class TestMeEndpoint:
    def test_requires_authentication(self, api):
        assert api.get(ME_URL).status_code == 401

    def test_exact_shape(self, api, user):
        api.force_authenticate(user)
        response = api.get(ME_URL)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"id", "email", "is_verified", "created_at", "profile_completed"}
        assert body["email"] == "me@example.com"
        assert body["is_verified"] is True
        assert body["profile_completed"] is False  # no profile yet → not complete

    def test_profile_completed_true_with_complete_profile(self, api, user):
        _complete_profile(user)
        api.force_authenticate(user)
        assert api.get(ME_URL).json()["profile_completed"] is True

    def test_profile_completed_false_with_partial_profile(self, api, user):
        # A profile row without offer_letter_date is incomplete: the wizard's
        # one nullable field is what separates "started" from "done".
        CandidateProfile.objects.create(
            user=user,
            display_name="Me Candidate",
            batch="2025",
            hiring_type=CandidateProfile.HiringType.DIGITAL,
            region="Hyderabad",
            offer_letter_date=None,
        )
        api.force_authenticate(user)
        assert api.get(ME_URL).json()["profile_completed"] is False

    def test_no_sensitive_fields_leak(self, api, user):
        api.force_authenticate(user)
        body = api.get(ME_URL).json()
        for forbidden in (
            "password",
            "is_staff",
            "is_superuser",
            "last_login",
            "groups",
            "user_permissions",
        ):
            assert forbidden not in body

    def test_ids_are_uuid_not_int(self, api, user):
        import uuid as uuid_lib

        api.force_authenticate(user)
        body = api.get(ME_URL).json()
        uuid_lib.UUID(str(body["id"]))  # raises if not a UUID
        assert str(body["id"]) == str(user.id)
