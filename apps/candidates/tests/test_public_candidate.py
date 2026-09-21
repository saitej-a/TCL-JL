"""Public candidate endpoint tests (04 §23; 3.2 D2): exact safe shape, AllowAny,
and redaction of everything else."""

import pytest

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/profile/"


def _public_url(profile) -> str:
    return f"/api/v1/candidates/{profile.id}/"


EXPECTED_KEYS = {"id", "display_name", "batch", "hiring_type", "region", "current_status"}


class TestPublicCandidate:
    def test_exact_23_shape(self, api, make_profile):
        profile = make_profile(display_name="Sai", public_identity_mode="DISPLAY_NAME")
        response = api.get(_public_url(profile))
        assert response.status_code == 200
        assert set(response.data.keys()) == EXPECTED_KEYS
        assert response.data["display_name"] == "Sai"
        assert response.data["current_status"] == "REGISTERED"

    def test_anonymous_mode_renders_pseudonym(self, api, make_profile):
        profile = make_profile(display_name="Sai")  # ANONYMOUS default
        response = api.get(_public_url(profile))
        assert response.status_code == 200
        assert response.data["display_name"] == "Anonymous Candidate"

    def test_blank_name_falls_back_to_anonymous(self, api, make_profile):
        profile = make_profile(display_name="", public_identity_mode="DISPLAY_NAME")
        response = api.get(_public_url(profile))
        assert response.data["display_name"] == "Anonymous Candidate"

    def test_no_pii_in_body(self, api, verified_user, make_profile):
        profile = make_profile(
            user=verified_user,
            display_name="Sai",
            public_identity_mode="DISPLAY_NAME",
            interview_center="Hyderabad",
        )
        response = api.get(_public_url(profile))
        body = str(response.content)
        assert verified_user.email not in body
        assert "email" not in response.data
        assert "interview_center" not in response.data
        assert "interview_date" not in response.data
        assert "user" not in response.data
        assert "created_at" not in response.data

    def test_missing_uuid_404_envelope(self, api):
        response = api.get("/api/v1/candidates/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == 404
        assert response.data["error"]["code"] == "profile_not_found"

    def test_unauthenticated_access_allowed(self, api, make_profile):
        profile = make_profile()
        response = api.get(_public_url(profile))
        assert response.status_code == 200

    def test_owner_private_route_still_requires_auth(self, api, make_profile):
        make_profile()
        assert api.get(PROFILE_URL).status_code == 401
        assert User.objects.count() >= 1  # sanity: suite isolated
