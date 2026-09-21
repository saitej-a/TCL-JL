"""Profile read/update tests (T3.5; 04 §19/§21; atomic PATCH)."""

import pytest

from apps.candidates.services import transition_status

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/profile/"


@pytest.fixture
def profile(verified_user, make_profile):
    """The profile under test belongs to verified_user — the API client's user."""
    return make_profile(user=verified_user, display_name="Sai", public_identity_mode="DISPLAY_NAME")


class TestRead:
    def test_get_exact_19_shape(self, api, verified_user, profile):
        api.force_authenticate(verified_user)
        response = api.get(PROFILE_URL)
        assert response.status_code == 200
        assert set(response.data.keys()) == {
            "id",
            "display_name",
            "public_identity_mode",
            "batch",
            "hiring_type",
            "region",
            "interview_center",
            "interview_date",
            "joining_location",
            "current_status",
            "offer_letter_date",
            "expected_joining_date",
            "created_at",
            "updated_at",
        }
        assert response.data["id"] == str(profile.id)
        assert "email" not in response.data

    def test_get_without_profile_404_envelope(self, api, verified_user):
        api.force_authenticate(verified_user)
        response = api.get(PROFILE_URL)
        assert response.status_code == 404
        assert response.data["error"]["code"] == "profile_not_found"

    def test_anonymous_401(self, api):
        assert api.get(PROFILE_URL).status_code == 401


class TestUpdate:
    def test_patch_region_ok(self, api, verified_user, profile):
        api.force_authenticate(verified_user)
        response = api.patch(PROFILE_URL, {"region": "Bengaluru"}, format="json")
        assert response.status_code == 200
        assert response.data["region"] == "Bengaluru"
        profile.refresh_from_db()
        assert profile.region == "Bengaluru"

    def test_patch_bad_batch_400(self, api, verified_user, profile):
        api.force_authenticate(verified_user)
        response = api.patch(PROFILE_URL, {"batch": "1999"}, format="json")
        assert response.status_code == 400
        assert "batch" in response.data

    def test_patch_legal_status_200(self, api, verified_user, profile):
        api.force_authenticate(verified_user)
        profile = transition_status(profile, "INTERVIEWED")
        response = api.patch(PROFILE_URL, {"current_status": "SELECTED"}, format="json")
        assert response.status_code == 200
        assert response.data["current_status"] == "SELECTED"
        profile.refresh_from_db()
        assert profile.current_status == "SELECTED"

    def test_patch_illegal_status_atomic_rollback(self, api, verified_user, profile):
        """Rejected transition must also roll back the same PATCH's field edit."""
        api.force_authenticate(verified_user)
        response = api.patch(
            PROFILE_URL,
            {"region": "Chennai", "current_status": "JOINED"},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "status_invalid_transition"
        profile.refresh_from_db()
        assert profile.region == "Telangana"  # field edit rolled back too
        assert profile.current_status == "REGISTERED"

    def test_patch_same_status_noop_ok(self, api, verified_user, profile):
        api.force_authenticate(verified_user)
        response = api.patch(PROFILE_URL, {"current_status": "REGISTERED"}, format="json")
        assert response.status_code == 200
        assert response.data["current_status"] == "REGISTERED"

    def test_patch_cannot_change_id_or_ownership(self, api, verified_user, profile):
        api.force_authenticate(verified_user)
        response = api.patch(
            PROFILE_URL, {"id": "00000000-0000-0000-0000-000000000000"}, format="json"
        )
        assert response.status_code == 200
        profile.refresh_from_db()
        assert str(profile.id) != "00000000-0000-0000-0000-000000000000"
        assert profile.user_id == verified_user.id

    def test_patch_reserved_display_name_400(self, api, verified_user, profile):
        api.force_authenticate(verified_user)
        response = api.patch(PROFILE_URL, {"display_name": "TCSOfficial"}, format="json")
        assert response.status_code == 400
        assert "display_name" in response.data
