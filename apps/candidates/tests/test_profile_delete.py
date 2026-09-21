"""DELETE /api/v1/profile/ behavior (04 §22; 3.2 D4): disallowed, envelope routes
candidates to account deletion."""

import pytest

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/profile/"


class TestDeleteDisallowed:
    def test_delete_returns_405_envelope(self, api, verified_user, make_profile):
        make_profile(user=verified_user)
        api.force_authenticate(verified_user)
        response = api.delete(PROFILE_URL)
        assert response.status_code == 405
        assert response.data["error"]["code"] == "method_not_allowed"
        assert "/api/v1/account/" in response.data["error"]["message"]

    def test_delete_leaves_account_and_profile_intact(self, api, verified_user, make_profile):
        make_profile(user=verified_user)
        api.force_authenticate(verified_user)
        api.delete(PROFILE_URL)
        verified_user.refresh_from_db()
        assert verified_user.is_active is True
        assert verified_user.candidate_profile is not None

    def test_delete_anonymous_gets_401(self, api):
        """Auth gate fires before method routing — anonymous never learns the
        method rules. Authenticated deletion remains 405 (test above)."""
        response = api.delete(PROFILE_URL)
        assert response.status_code == 401
