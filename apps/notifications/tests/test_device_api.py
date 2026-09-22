"""Tests for Device API endpoints (Phase 6.2 — 07 §11.4–§11.6, D6, D7, R6, R7)."""

from __future__ import annotations

import uuid

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status

from apps.notifications.models import Device


def test_register_device_success_201_omits_fcm_token(auth_api):
    client, user = auth_api()
    payload = {
        "fcm_token": "valid-sample-fcm-token-12345",
        "device_type": "WEB",
        "browser": "Firefox on Linux",
    }
    response = client.post("/api/v1/devices/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "fcm_token" not in data
    assert data["device_type"] == "WEB"
    assert data["browser"] == "Firefox on Linux"
    assert data["is_active"] is True
    assert "id" in data
    assert "last_seen_at" in data
    assert "created_at" in data

    device = Device.objects.get(id=data["id"])
    assert device.user == user
    assert device.fcm_token == "valid-sample-fcm-token-12345"


def test_list_devices_200_active_only_omits_fcm_token(auth_api, make_device):
    client, user = auth_api()
    make_device(user=user, fcm_token="secret-token-active-1")
    make_device(user=user, fcm_token="secret-token-active-2")

    response = client.get("/api/v1/devices/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] == 2
    for item in data["results"]:
        assert "fcm_token" not in item
        assert item["is_active"] is True


def test_reassignment_moves_device_to_new_user_and_returns_201(auth_api):
    client_a, user_a = auth_api("user_a@example.com")
    client_b, user_b = auth_api("user_b@example.com")

    token = "shared-hardware-fcm-token-999"
    # User A registers
    res_a = client_a.post("/api/v1/devices/", {"fcm_token": token, "browser": "Edge"})
    assert res_a.status_code == status.HTTP_201_CREATED

    device = Device.objects.get(fcm_token=token)
    assert device.user == user_a
    original_id = device.id

    # User B registers same token (D6: last-writer-wins reassignment)
    res_b = client_b.post(
        "/api/v1/devices/",
        {"fcm_token": token, "browser": "Chrome"},
    )
    assert res_b.status_code == status.HTTP_201_CREATED

    device.refresh_from_db()
    assert device.id == original_id
    assert device.user == user_b
    assert device.browser == "Chrome"
    assert device.is_active is True


def test_re_registering_revoked_token_reactivates_device(auth_api):
    client, user = auth_api()
    token = "token-to-be-revoked-and-revived"

    res1 = client.post("/api/v1/devices/", {"fcm_token": token})
    assert res1.status_code == status.HTTP_201_CREATED
    device_id = res1.json()["id"]

    # Soft-revoke
    res_del = client.delete(f"/api/v1/devices/{device_id}/")
    assert res_del.status_code == status.HTTP_204_NO_CONTENT

    device = Device.objects.get(id=device_id)
    assert device.is_active is False

    # Re-register same token
    res2 = client.post("/api/v1/devices/", {"fcm_token": token, "browser": "Safari"})
    assert res2.status_code == status.HTTP_201_CREATED
    device.refresh_from_db()
    assert device.is_active is True
    assert device.browser == "Safari"


def test_list_devices_returns_active_devices_ordered_by_last_seen_at(auth_api, make_device):
    client, user = auth_api()
    d1 = make_device(user=user, browser="Browser 1")
    d2 = make_device(user=user, browser="Browser 2")

    response = client.get("/api/v1/devices/")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    ids = [r["id"] for r in results]
    # Ordered -last_seen_at
    assert ids == [str(d2.id), str(d1.id)]


def test_list_devices_excludes_revoked_devices(auth_api, make_device):
    client, user = auth_api()
    active_d = make_device(user=user, is_active=True)
    make_device(user=user, is_active=False)

    response = client.get("/api/v1/devices/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == str(active_d.id)


def test_list_devices_is_owner_scoped(auth_api, make_device):
    client_a, user_a = auth_api("owner_a@example.com")
    client_b, user_b = auth_api("owner_b@example.com")
    make_device(user=user_a)

    res_b = client_b.get("/api/v1/devices/")
    assert res_b.status_code == status.HTTP_200_OK
    assert res_b.json()["count"] == 0


def test_list_devices_performs_only_selects_zero_writes(api, make_device):
    make_device(user=api.user)
    with CaptureQueriesContext(connection) as queries:
        response = api.get("/api/v1/devices/")
        assert response.status_code == status.HTTP_200_OK

    query_sqls = [q["sql"].strip().upper() for q in queries]
    for sql in query_sqls:
        assert not sql.startswith("INSERT")
        assert not sql.startswith("UPDATE")
        assert not sql.startswith("DELETE")


def test_delete_device_soft_revokes_with_204(auth_api, make_device):
    client, user = auth_api()
    device = make_device(user=user, is_active=True)

    response = client.delete(f"/api/v1/devices/{device.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # D7: Device is NEVER deleted from DB
    assert Device.objects.filter(id=device.id).exists()
    device.refresh_from_db()
    assert device.is_active is False


def test_delete_foreign_device_returns_404_envelope(auth_api, make_device):
    client_a, user_a = auth_api("user_a_owner@example.com")
    client_b, user_b = auth_api("user_b_attacker@example.com")
    device_a = make_device(user=user_a, is_active=True)

    res = client_b.delete(f"/api/v1/devices/{device_a.id}/")
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json() == {
        "error": {
            "code": "device_not_found",
            "message": "Device not found.",
        }
    }


def test_delete_already_revoked_device_returns_404_envelope(auth_api, make_device):
    client, user = auth_api()
    device = make_device(user=user, is_active=False)

    res = client.delete(f"/api/v1/devices/{device.id}/")
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json() == {
        "error": {
            "code": "device_not_found",
            "message": "Device not found.",
        }
    }


def test_delete_malformed_uuid_returns_404_envelope(auth_api):
    client, user = auth_api()
    res = client.delete("/api/v1/devices/not-a-valid-uuid-format/")
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json() == {
        "error": {
            "code": "device_not_found",
            "message": "Device not found.",
        }
    }


def test_anonymous_request_returns_401(anon_api):
    assert anon_api.get("/api/v1/devices/").status_code == status.HTTP_401_UNAUTHORIZED
    res_post = anon_api.post("/api/v1/devices/", {"fcm_token": "token"})
    assert res_post.status_code == status.HTTP_401_UNAUTHORIZED


def test_unverified_user_returns_403(auth_api):
    client, user = auth_api(is_verified=False)
    assert client.get("/api/v1/devices/").status_code == status.HTTP_403_FORBIDDEN
    res_post = client.post("/api/v1/devices/", {"fcm_token": "token"})
    assert res_post.status_code == status.HTTP_403_FORBIDDEN


def test_device_registration_throttle_429_on_11th_attempt(auth_api):
    client, user = auth_api()
    for idx in range(10):
        token = f"throttle-test-token-{uuid.uuid4()}"
        res = client.post("/api/v1/devices/", {"fcm_token": token})
        assert res.status_code == status.HTTP_201_CREATED, f"Failed on step {idx}: {res.content}"

    # 11th registration in the hour
    res_11 = client.post(
        "/api/v1/devices/",
        {"fcm_token": f"throttle-test-token-{uuid.uuid4()}"},
    )
    assert res_11.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    data = res_11.json()
    assert "error" in data
    assert data["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in res_11.headers


def test_invalid_payloads_return_400(auth_api):
    client, user = auth_api()

    # Blank token
    res_blank = client.post("/api/v1/devices/", {"fcm_token": "   "})
    assert res_blank.status_code == status.HTTP_400_BAD_REQUEST

    # Oversize token (> 4096)
    res_oversize = client.post("/api/v1/devices/", {"fcm_token": "x" * 4097})
    assert res_oversize.status_code == status.HTTP_400_BAD_REQUEST

    # Invalid device_type
    res_invalid_type = client.post(
        "/api/v1/devices/",
        {"fcm_token": "valid-token", "device_type": "SMARTWATCH"},
    )
    assert res_invalid_type.status_code == status.HTTP_400_BAD_REQUEST
