"""Account deletion tests (04 §78, 06 §2.7; AUTH-05)."""

import re

import pytest
from django.test import override_settings
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

DELETE_URL = "/api/v1/account/"
LOGIN_URL = "/api/v1/auth/login/"
GENERIC_403 = "Invalid email or password."
VALID_PASSWORD = "Correct Horse Battery 9!"


@pytest.fixture
def user():
    return User.objects.create_user("doomed@example.com", VALID_PASSWORD, is_verified=True)


def _delete(api, payload):
    return api.delete(DELETE_URL, data=payload, content_type="application/json")


class TestDeletionAuth:
    def test_requires_authentication(self, api):
        response = _delete(api, {"password": VALID_PASSWORD})
        assert response.status_code == 401

    def test_wrong_password_generic_403(self, api, user):
        api.force_authenticate(user)
        response = _delete(api, {"password": "WrongPassword123!"})
        assert response.status_code == 403
        # Generic message: reveals nothing about account state beyond authz failure.
        assert "deleted" not in response.content.decode().lower()


class TestDeletionSuccess:
    def test_delete_returns_204(self, api, user):
        api.force_authenticate(user)
        response = _delete(api, {"password": VALID_PASSWORD})
        assert response.status_code == 204

    def test_row_retained_and_anonymized(self, api, user):
        api.force_authenticate(user)
        _delete(api, {"password": VALID_PASSWORD})
        user.refresh_from_db()
        assert User.objects.filter(pk=user.pk).exists()  # tombstone seam for Phase 5
        assert re.fullmatch(r"deleted_[0-9a-f]{32}@tracker\.internal", user.email)
        assert user.is_active is False
        assert user.is_verified is False
        assert user.has_usable_password() is False

    def test_all_refresh_tokens_blacklisted(self, api, user):
        login = api.post(
            LOGIN_URL, {"email": user.email, "password": VALID_PASSWORD}, content_type="application/json"
        ).json()
        api.force_authenticate(user)
        _delete(api, {"password": VALID_PASSWORD})
        with pytest.raises(TokenError):
            RefreshToken(login["refresh"])

    def test_cannot_login_after_deletion(self, api, user):
        api.force_authenticate(user)
        _delete(api, {"password": VALID_PASSWORD})
        response = api.post(
            LOGIN_URL, {"email": "doomed@example.com", "password": VALID_PASSWORD}, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}

    def test_deleted_email_never_leaks_original(self, api, user):
        api.force_authenticate(user)
        _delete(api, {"password": VALID_PASSWORD})
        user.refresh_from_db()
        assert "doomed@example.com" != user.email
        assert "doomed" not in user.email
