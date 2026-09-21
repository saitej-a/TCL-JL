"""``IsVerified`` permission tests (plan deliverable; Phase 5 will consume it)."""

import pytest

from apps.accounts.models import User
from apps.accounts.permissions import IsVerified

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "Correct Horse Battery 9!"


class _Request:
    def __init__(self, user):
        self.user = user


class _User:
    is_authenticated = True


class TestIsVerified:
    def test_verified_user_admitted(self):
        user = User.objects.create_user("ok@example.com", VALID_PASSWORD, is_verified=True)
        assert IsVerified().has_permission(_Request(user), None) is True

    def test_unverified_user_rejected(self):
        user = User.objects.create_user("pending@example.com", VALID_PASSWORD, is_verified=False)
        assert IsVerified().has_permission(_Request(user), None) is False

    def test_anonymous_rejected(self):
        class _Anon:
            is_authenticated = False

        assert IsVerified().has_permission(_Request(_Anon()), None) is False
