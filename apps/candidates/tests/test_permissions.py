"""Ownership permission tests (T3.5/T3.8; 3.2 invariants)."""

import pytest
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.candidates.permissions import IsProfileOwner

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/profile/"
VALID_PASSWORD = "Correct Horse Battery 9!"


def _drf_request(user):
    factory = APIRequestFactory()
    request = factory.get(PROFILE_URL)
    request.user = user
    return request


class TestIsProfileOwner:
    def test_owner_true(self, verified_user, make_profile):
        profile = make_profile(user=verified_user)
        assert IsProfileOwner().has_object_permission(_drf_request(verified_user), None, profile)

    def test_other_user_false(self, verified_user, make_profile):
        profile = make_profile(user=verified_user)
        other = User.objects.create_user("other@example.com", VALID_PASSWORD, is_verified=True)
        assert IsProfileOwner().has_object_permission(_drf_request(other), None, profile) is False

    def test_anonymous_false(self, verified_user, make_profile):
        profile = make_profile(user=verified_user)
        assert IsProfileOwner().has_object_permission(_drf_request(None), None, profile) is False

    def test_orphan_profile_false(self, make_profile):
        """Profile-less row (user NULL — allowed by 3.1 D4) admits nobody."""
        profile = make_profile(user=None)
        someone = User.objects.create_user("somebody@example.com", VALID_PASSWORD, is_verified=True)
        assert IsProfileOwner().has_object_permission(_drf_request(someone), None, profile) is False


class TestViewGating:
    def test_unverified_user_blocked_from_profile_routes(self, api, unverified_user, make_profile):
        make_profile(user=unverified_user)
        api.force_authenticate(unverified_user)
        assert api.get(PROFILE_URL).status_code == 403
        assert api.patch(PROFILE_URL, {"region": "X"}, format="json").status_code == 403
        assert api.post(PROFILE_URL, {}, format="json").status_code == 403

    def test_verified_user_allowed(self, api, verified_user, make_profile):
        make_profile(user=verified_user)
        api.force_authenticate(verified_user)
        assert api.get(PROFILE_URL).status_code == 200
