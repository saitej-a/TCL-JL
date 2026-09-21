"""Password reset tests (04 §17, 06 §3.5; AUTH-03)."""

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.services import (
    confirm_password_reset,
    make_password_reset_token,
    request_password_reset,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def eager_celery(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True

RESET_REQUEST_URL = "/api/v1/auth/password-reset/request/"
RESET_CONFIRM_URL = "/api/v1/auth/password-reset/confirm/"
LOGIN_URL = "/api/v1/auth/login/"
GENERIC_MESSAGE = (
    "If an account exists with this email, password reset instructions have been dispatched."
)
VALID_PASSWORD = "Correct Horse Battery 9!"
NEW_PASSWORD = "Brand New Steel Vault 7!"


@pytest.fixture
def user():
    return User.objects.create_user("resetter@example.com", VALID_PASSWORD, is_verified=True)


class TestResetRequest:
    @pytest.mark.django_db(transaction=True)
    def test_valid_email_dispatches_reset_email(self, client, user):
        mail.outbox.clear()
        response = client.post(RESET_REQUEST_URL, {"email": user.email}, content_type="application/json")
        assert response.status_code == 200
        assert len(mail.outbox) == 1

    @pytest.mark.django_db(transaction=True)
    def test_unknown_email_generic_200_no_dispatch(self, client, user):
        mail.outbox.clear()
        response = client.post(RESET_REQUEST_URL, {"email": "nobody@example.com"}, content_type="application/json")
        assert response.status_code == 200
        assert len(mail.outbox) == 0

    def test_response_body_generic(self, client, user):
        response = client.post(RESET_REQUEST_URL, {"email": user.email}, content_type="application/json")
        assert response.status_code == 200
        assert response.json() == {"message": GENERIC_MESSAGE}

    def test_throttled_to_3_per_hour(self, client, user):
        for _ in range(3):
            assert client.post(
                RESET_REQUEST_URL, {"email": user.email}, content_type="application/json"
            ).status_code == 200
        fourth = client.post(RESET_REQUEST_URL, {"email": user.email}, content_type="application/json")
        assert fourth.status_code == 429


class TestResetConfirm:
    def test_confirm_rotates_hash_and_rejects_old_password(self, user):
        token = make_password_reset_token(user)
        confirm = confirm_password_reset(token, NEW_PASSWORD)
        assert confirm.pk == user.pk
        assert not user.check_password(VALID_PASSWORD)
        assert user.check_password(NEW_PASSWORD)

    def test_token_single_use_after_hash_rotation(self, user):
        token = make_password_reset_token(user)
        confirm_password_reset(token, NEW_PASSWORD)
        with pytest.raises(ValueError):
            confirm_password_reset(token, "Another Steel Vault 8!")

    def test_confirm_revokes_outstanding_refresh_tokens(self, user):
        login = user_login(user)
        confirm_password_reset(make_password_reset_token(user), NEW_PASSWORD)
        with pytest.raises(TokenError):
            RefreshToken(login["refresh"])

    def test_expired_token_rejected(self, user):
        with override_settings(PASSWORD_RESET_TIMEOUT=0):
            token = make_password_reset_token(user)
        with pytest.raises(ValueError):
            confirm_password_reset(token, NEW_PASSWORD)

    def test_tampered_token_rejected(self, user):
        token = make_password_reset_token(user)
        bad = token[:-1] + ("0" if token[-1] != "0" else "1")
        with pytest.raises(ValueError):
            confirm_password_reset(bad, NEW_PASSWORD)


class TestResetFlowHTTP:
    @pytest.mark.django_db(transaction=True)
    def test_full_round_trip_via_http(self, client, user):
        # 1. request
        response = client.post(RESET_REQUEST_URL, {"email": user.email}, content_type="application/json")
        assert response.status_code == 200
        assert len(mail.outbox) == 1
        # 2. extract link from the console email
        body = mail.outbox[0].body
        assert "reset-password/" in body
        token = body.split("reset-password/")[1].split()[0]
        # 3. confirm via HTTP
        confirm = client.post(
            RESET_CONFIRM_URL,
            {"token": token, "new_password": NEW_PASSWORD, "new_password_confirm": NEW_PASSWORD},
            content_type="application/json",
        )
        assert confirm.status_code == 200
        assert confirm.json() == {"message": "Password reset successfully."}
        # 4. old password no longer logs in; new one does
        old_login = client.post(
            LOGIN_URL, {"email": user.email, "password": VALID_PASSWORD}, content_type="application/json"
        )
        assert old_login.status_code == 401
        new_login = client.post(
            LOGIN_URL, {"email": user.email, "password": NEW_PASSWORD}, content_type="application/json"
        )
        assert new_login.status_code == 200

    def test_confirm_password_mismatch_400(self, client, user):
        token = make_password_reset_token(user)
        response = client.post(
            RESET_CONFIRM_URL,
            {"token": token, "new_password": NEW_PASSWORD, "new_password_confirm": "Different 123!"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_confirm_weak_password_400(self, client, user):
        token = make_password_reset_token(user)
        response = client.post(
            RESET_CONFIRM_URL,
            {"token": token, "new_password": "alllowercase123!", "new_password_confirm": "alllowercase123!"},
            content_type="application/json",
        )
        assert response.status_code == 400


def user_login(user):
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        LOGIN_URL, {"email": user.email, "password": VALID_PASSWORD}, content_type="application/json"
    )
    assert response.status_code == 200
    return response.json()
