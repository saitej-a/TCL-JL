"""Logout tests (04 §16): refresh-token blacklist + 204."""

import pytest
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

LOGOUT_URL = "/api/v1/auth/logout/"
LOGIN_URL = "/api/v1/auth/login/"
VALID_PASSWORD = "Correct Horse Battery 9!"


def _login(client, email="logout@example.com"):
    response = client.post(
        LOGIN_URL, {"email": email, "password": VALID_PASSWORD}, content_type="application/json"
    )
    assert response.status_code == 200
    return response.json()


class TestLogout:
    def test_logout_blacklists_refresh_and_returns_204(self, client):
        tokens = _login(client)
        response = client.post(
            LOGOUT_URL, {"refresh": tokens["refresh"]}, content_type="application/json"
        )
        assert response.status_code == 204
        with pytest.raises(TokenError):
            RefreshToken(tokens["refresh"])  # blacklisted

    def test_logout_requires_authentication(self, client):
        response = client.post(LOGOUT_URL, {"refresh": "anything"}, content_type="application/json")
        assert response.status_code == 401

    def test_logout_rejects_token_of_other_account(self, client):
        tokens = _login(client, "owner@example.com")
        User.objects.create_user("attacker@example.com", VALID_PASSWORD)
        attacker = _login(client, "attacker@example.com")
        client.force_authenticate(User.objects.get(email="attacker@example.com"))
        response = client.post(LOGOUT_URL, {"refresh": tokens["refresh"]}, content_type="application/json")
        assert response.status_code == 400
        # The owner's refresh is untouched.
        RefreshToken(tokens["refresh"])  # must not raise
        assert attacker["access"]

    def test_logout_malformed_token_400(self, client):
        tokens = _login(client)
        client.force_authenticate(User.objects.get(email="logout@example.com"))
        response = client.post(LOGOUT_URL, {"refresh": "garbage-token"}, content_type="application/json")
        assert response.status_code == 400
