"""Profile creation tests (T3.4; 3.2 D1)."""

import pytest

from apps.candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/profile/"

CREATE_BODY = {
    "display_name": "Sai",
    "public_identity_mode": "DISPLAY_NAME",
    "batch": "2025",
    "hiring_type": "DIGITAL",
    "region": "Telangana",
    "interview_center": "Hyderabad",
}


class TestCreateSuccess:
    def test_create_returns_201_and_exact_shape(self, api, verified_user):
        api.force_authenticate(verified_user)
        response = api.post(PROFILE_URL, CREATE_BODY, format="json")
        assert response.status_code == 201
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
        assert response.data["current_status"] == "REGISTERED"
        profile = CandidateProfile.objects.get(user=verified_user)
        assert profile.public_identity_mode == "DISPLAY_NAME"

    def test_create_defaults_anonymous_when_mode_omitted(self, api, verified_user):
        api.force_authenticate(verified_user)
        body = {k: v for k, v in CREATE_BODY.items() if k != "public_identity_mode"}
        body["display_name"] = ""
        response = api.post(PROFILE_URL, body, format="json")
        assert response.status_code == 201
        assert response.data["public_identity_mode"] == "ANONYMOUS"

    def test_d1_requested_status_honored_via_transition_chain(self, api, verified_user):
        api.force_authenticate(verified_user)
        body = {**CREATE_BODY, "current_status": "INTERVIEWED"}
        response = api.post(PROFILE_URL, body, format="json")
        assert response.status_code == 201
        assert response.data["current_status"] == "INTERVIEWED"
        profile = CandidateProfile.objects.get(user=verified_user)
        profile.refresh_from_db()
        assert profile.current_status == "INTERVIEWED"


class TestCreateRejections:
    def test_duplicate_creation_409_envelope(self, api, verified_user, make_profile):
        make_profile(user=verified_user)
        api.force_authenticate(verified_user)
        response = api.post(PROFILE_URL, CREATE_BODY, format="json")
        assert response.status_code == 409
        assert response.data["error"]["code"] == "profile_exists"
        assert CandidateProfile.objects.filter(user=verified_user).count() == 1

    def test_unverified_user_403(self, api, unverified_user):
        api.force_authenticate(unverified_user)
        response = api.post(PROFILE_URL, CREATE_BODY, format="json")
        assert response.status_code == 403

    def test_inactive_user_403(self, api, inactive_user):
        api.force_authenticate(inactive_user)
        response = api.post(PROFILE_URL, CREATE_BODY, format="json")
        assert response.status_code == 403

    def test_anonymous_401(self, api):
        response = api.post(PROFILE_URL, CREATE_BODY, format="json")
        assert response.status_code == 401

    def test_d1_illegal_status_400_and_no_profile_created(self, api, verified_user):
        api.force_authenticate(verified_user)
        body = {**CREATE_BODY, "current_status": "WAITING_FOR_JOINING_LETTER"}
        response = api.post(PROFILE_URL, body, format="json")
        assert response.status_code == 400
        assert response.data["error"]["code"] == "status_invalid_transition"
        assert not CandidateProfile.objects.filter(user=verified_user).exists()

    def test_d1_skip_to_joined_400(self, api, verified_user):
        api.force_authenticate(verified_user)
        body = {**CREATE_BODY, "current_status": "JOINED"}
        response = api.post(PROFILE_URL, body, format="json")
        assert response.status_code == 400
        assert not CandidateProfile.objects.filter(user=verified_user).exists()

    def test_unoffered_batch_400(self, api, verified_user):
        api.force_authenticate(verified_user)
        body = {**CREATE_BODY, "batch": "2027"}
        response = api.post(PROFILE_URL, body, format="json")
        assert response.status_code == 400
        assert "batch" in response.data
