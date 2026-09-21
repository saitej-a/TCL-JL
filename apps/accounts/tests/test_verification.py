"""Email verification tests (04 §13, 06 §2.5; AUTH-02)."""

from unittest import mock

import pytest
from django.core import mail

from apps.accounts.models import User
from apps.accounts.services import make_verification_token

pytestmark = pytest.mark.django_db

VERIFY_URL = "/api/v1/auth/verification/verify/"
RESEND_URL = "/api/v1/auth/verification/resend/"
GENERIC_RESEND_MESSAGE = "If an unverified account exists, a verification link has been sent."
VALID_PASSWORD = "Correct Horse Battery 9!"


def _make_user(email="unverified@example.com", verified=False):
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={"is_verified": verified},
    )
    return user


class TestVerifyEndpoint:
    def test_valid_token_verifies_account(self, client):
        user = _make_user()
        response = client.post(
            VERIFY_URL, {"token": make_verification_token(user)}, content_type="application/json"
        )
        assert response.status_code == 200
        assert response.json() == {"message": "Email verified successfully."}
        user.refresh_from_db()
        assert user.is_verified is True

    def test_expired_token_rejected(self, client):
        """Signature valid but older than the 24h window → expired path."""
        user = _make_user()
        token = make_verification_token(user)
        with mock.patch("apps.accounts.services.EMAIL_VERIFY_MAX_AGE", 0):
            response = client.post(VERIFY_URL, {"token": token}, content_type="application/json")
        assert response.status_code == 400
        user.refresh_from_db()
        assert user.is_verified is False

    def test_reuse_after_verify_rejected(self, client):
        user = _make_user()
        token = make_verification_token(user)
        first = client.post(VERIFY_URL, {"token": token}, content_type="application/json")
        assert first.status_code == 200
        second = client.post(VERIFY_URL, {"token": token}, content_type="application/json")
        assert second.status_code == 400

    def test_garbage_token_rejected(self, client):
        response = client.post(
            VERIFY_URL, {"token": "not-a-token"}, content_type="application/json"
        )
        assert response.status_code == 400


class TestResendEndpoint:
    @pytest.mark.django_db(transaction=True)
    def test_generic_body_for_unverified_user_and_email_sent(self, client):
        _make_user("resend-target@example.com")
        mail.outbox.clear()
        response = client.post(
            RESEND_URL, {"email": "resend-target@example.com"}, content_type="application/json"
        )
        assert response.status_code == 200
        assert response.json() == {"message": GENERIC_RESEND_MESSAGE}
        assert len(mail.outbox) == 1

    def test_generic_body_for_unknown_email_no_dispatch(self, client):
        mail.outbox.clear()
        response = client.post(
            RESEND_URL, {"email": "nobody@example.com"}, content_type="application/json"
        )
        assert response.status_code == 200
        assert response.json() == {"message": GENERIC_RESEND_MESSAGE}
        assert len(mail.outbox) == 0

    def test_generic_body_for_already_verified_no_dispatch(self, client):
        _make_user(verified=True)
        mail.outbox.clear()
        response = client.post(
            RESEND_URL, {"email": "unverified@example.com"}, content_type="application/json"
        )
        assert response.status_code == 200
        assert len(mail.outbox) == 0

    def test_resend_throttled_to_1_per_minute(self, client):
        client.post(
            RESEND_URL, {"email": "unverified@example.com"}, content_type="application/json"
        )
        second = client.post(
            RESEND_URL, {"email": "unverified@example.com"}, content_type="application/json"
        )
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "RATE_LIMITED"
