"""Suspended-login tests (Phase 8.2 — D1/§6.2; 08_MODERATION.md §6.2)."""

import pytest

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login/"
GENERIC_ERROR = {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}
SUSPENDED_ERROR = {
    "error": {
        "code": "ACCOUNT_SUSPENDED",
        "message": "This account has been suspended for violating community guidelines.",
    }
}
VALID_PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture
def banned_user(db):
    return User.objects.create_user(
        "suspended@example.com", VALID_PASSWORD, is_verified=True, is_active=False
    )


class TestSuspendedLogin:
    def test_correct_password_returns_account_suspended_403(self, client, banned_user):
        response = client.post(
            LOGIN_URL,
            {"email": banned_user.email, "password": VALID_PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == 403
        assert response.json() == SUSPENDED_ERROR

    def test_wrong_password_stays_generic(self, client, banned_user):
        """Anti-enumeration: a banned account with a wrong password must be
        indistinguishable from any other failed login."""
        response = client.post(
            LOGIN_URL,
            {"email": banned_user.email, "password": "WrongPassword1!"},
            content_type="application/json",
        )
        assert response.status_code == 401
        assert response.json() == GENERIC_ERROR

    def test_unknown_email_stays_generic(self, client, banned_user):
        response = client.post(
            LOGIN_URL,
            {"email": "nobody@example.com", "password": VALID_PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == 401
        assert response.json() == GENERIC_ERROR

    def test_unban_restores_login(self, client, banned_user):
        banned_user.is_active = True
        banned_user.save(update_fields=["is_active"])
        response = client.post(
            LOGIN_URL,
            {"email": banned_user.email, "password": VALID_PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "access" in response.json()
