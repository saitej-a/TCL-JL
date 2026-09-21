"""``GET /me/`` tests (04 §18, 06 §5.2): exact shape, zero sensitive leakage."""

import pytest

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

ME_URL = "/api/v1/me/"
VALID_PASSWORD = "Correct Horse Battery 9!"


@pytest.fixture
def user():
    return User.objects.create_user("me@example.com", VALID_PASSWORD, is_verified=True)


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
        assert body["profile_completed"] is False  # CandidateProfile lands Phase 3.1

    def test_no_sensitive_fields_leak(self, api, user):
        api.force_authenticate(user)
        body = api.get(ME_URL).json()
        for forbidden in ("password", "is_staff", "is_superuser", "last_login", "groups", "user_permissions"):
            assert forbidden not in body

    def test_ids_are_uuid_not_int(self, api, user):
        import uuid as uuid_lib

        api.force_authenticate(user)
        body = api.get(ME_URL).json()
        uuid_lib.UUID(str(body["id"]))  # raises if not a UUID
        assert str(body["id"]) == str(user.id)
