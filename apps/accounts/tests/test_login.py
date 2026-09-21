"""Login tests (04 §14, 06 §2.6/§7.2; AUTH-06 anti-enumeration + throttling)."""

import pytest
from django.test import override_settings

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login/"
GENERIC_ERROR = {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}
VALID_PASSWORD = "Correct Horse Battery 9!"


def _make_user(email="login@example.com", verified=True, active=True):
    return User.objects.create_user(email, VALID_PASSWORD, is_verified=verified, is_active=active)


class TestLoginSuccess:
    def test_returns_tokens_and_user_block(self, client):
        user = _make_user()
        response = client.post(
            LOGIN_URL,
            {"email": user.email, "password": VALID_PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= {"access", "refresh", "user"}
        assert body["user"]["email"] == "login@example.com"
        assert body["user"]["is_verified"] is True
        assert "password" not in body["user"]

    def test_login_is_case_insensitive_on_email(self, client):
        _make_user("Mixed@Example.COM")
        response = client.post(
            LOGIN_URL,
            {"email": "mixed@example.com", "password": VALID_PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_unverified_user_logs_in_with_flag_false(self, client):
        """06 §2.6: unverified users receive tokens; is_verified surfaces false."""
        _make_user(verified=False)
        response = client.post(
            LOGIN_URL,
            {"email": "login@example.com", "password": VALID_PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["user"]["is_verified"] is False


class TestLoginFailuresGeneric:
    """Identical body for unknown email, wrong password, banned account (04 §14)."""

    def _login(self, client, email, password):
        return client.post(
            LOGIN_URL, {"email": email, "password": password}, content_type="application/json"
        )

    def test_unknown_email(self, client):
        response = self._login(client, "ghost@example.com", VALID_PASSWORD)
        assert response.status_code == 401
        assert response.json() == GENERIC_ERROR

    def test_wrong_password(self, client):
        _make_user()
        response = self._login(client, "login@example.com", "WrongPassword123!")
        assert response.status_code == 401
        assert response.json() == GENERIC_ERROR

    def test_banned_account_same_body(self, client):
        """06 §2.6: is_active=False → 401, indistinguishable from bad creds."""
        _make_user(active=False)
        response = self._login(client, "login@example.com", VALID_PASSWORD)
        assert response.status_code == 401
        assert response.json() == GENERIC_ERROR


class TestLoginThrottle:
    @override_settings()
    def test_6th_attempt_429_with_retry_after(self, client):
        _make_user()
        payload = {"email": "login@example.com", "password": "WrongPassword123!"}
        codes = [
            client.post(LOGIN_URL, payload, content_type="application/json").status_code
            for _ in range(5)
        ]
        assert codes == [401] * 5
        sixth = client.post(LOGIN_URL, payload, content_type="application/json")
        assert sixth.status_code == 429
        assert "Retry-After" in sixth
        assert sixth.json()["error"]["code"] == "RATE_LIMITED"

    @override_settings()
    def test_combined_bucket_does_not_collateral_block_other_emails(self, client):
        """Same IP, different email → separate bucket (06 §7.2 semantics)."""
        _make_user("a@example.com")
        _make_user("b@example.com")
        bad = {"email": "a@example.com", "password": "WrongPassword123!"}
        for _ in range(5):
            client.post(LOGIN_URL, bad, content_type="application/json")
        assert client.post(LOGIN_URL, bad, content_type="application/json").status_code == 429
        other = client.post(
            LOGIN_URL,
            {"email": "b@example.com", "password": VALID_PASSWORD},
            content_type="application/json",
        )
        assert other.status_code == 200
