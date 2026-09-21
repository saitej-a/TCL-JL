"""JWT rotation + family reuse-detection tests (06 §3.1/§3.2; AUTH-04).

Headline success criterion 3: replaying a rotated refresh token revokes the
whole session family. Also pins the claim hygiene rules (no email/PII).
"""

import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.serializers import FamilyTokenObtainPairSerializer, FamilyTokenRefreshSerializer

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "Correct Horse Battery 9!"


@pytest.fixture
def user():
    return User.objects.create_user("rotator@example.com", VALID_PASSWORD, is_verified=True)


@pytest.fixture
def tokens(user):
    serializer = FamilyTokenObtainPairSerializer(
        data={"email": user.email, "password": VALID_PASSWORD}
    )
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _refresh(raw):
    serializer = FamilyTokenRefreshSerializer(data={"refresh": raw})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class TestRotation:
    def test_rotate_issues_new_refresh_and_access(self, tokens):
        rotated = _refresh(tokens["refresh"])
        assert rotated["refresh"] != tokens["refresh"]
        assert rotated["access"]

    def test_rotation_keeps_family_claim(self, tokens):
        original_fam = token_backend.decode(tokens["refresh"], verify=True)["fam"]
        rotated_fam = token_backend.decode(_refresh(tokens["refresh"])["refresh"], verify=True)["fam"]
        assert original_fam == rotated_fam

    def test_child_recorded_outstanding(self, user, tokens):
        assert OutstandingToken.objects.filter(user=user).count() == 1  # login refresh
        rotated = _refresh(tokens["refresh"])
        assert OutstandingToken.objects.filter(user=user).count() == 2  # + child


class TestReplayRevokesFamily:
    """The headline criterion — replay kills the entire token family."""

    def test_replayed_refresh_401_and_child_dead(self, user, tokens):
        rotated = _refresh(tokens["refresh"])
        child = rotated["refresh"]

        with pytest.raises(AuthenticationFailed):
            _refresh(tokens["refresh"])  # replay of the already-rotated token

        # The child minted before the replay must be dead too (family revoked).
        with pytest.raises(TokenError):
            RefreshToken(child)

    def test_family_blacklist_covers_login_and_child(self, user, tokens):
        _refresh(tokens["refresh"])
        with pytest.raises(AuthenticationFailed):
            _refresh(tokens["refresh"])
        assert BlacklistedToken.objects.count() >= 2


class TestClaimHygiene:
    """Access payload carries UUID + is_verified only — never email/PII (06 §3.1.1)."""

    FORBIDDEN_CLAIMS = {"email", "username", "first_name", "last_name", "is_staff"}

    def test_refresh_payload_has_no_pii(self, user, tokens):
        payload = token_backend.decode(tokens["refresh"], verify=True)
        assert payload[api_settings.USER_ID_CLAIM] == str(user.id)
        assert self.FORBIDDEN_CLAIMS.isdisjoint(payload)

    def test_access_payload_has_no_pii_and_is_verified_claim(self, user, tokens):
        payload = token_backend.decode(tokens["access"], verify=True)
        assert payload[api_settings.USER_ID_CLAIM] == str(user.id)
        assert payload["is_verified"] is True
        assert self.FORBIDDEN_CLAIMS.isdisjoint(payload)

    def test_fam_claim_present(self, user, tokens):
        payload = token_backend.decode(tokens["refresh"], verify=True)
        assert payload.get("fam")
