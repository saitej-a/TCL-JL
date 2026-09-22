"""Tests for Notification Preferences API endpoints (Phase 6.2 — 07 §8, §11.7, D13, R3)."""

from __future__ import annotations

from rest_framework import status

from apps.notifications.models import NotificationPreference


def test_get_preferences_lazy_creation_returns_all_true_defaults(auth_api):
    client, user = auth_api()
    assert not NotificationPreference.objects.filter(user=user).exists()

    response = client.get("/api/v1/notifications/preferences/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["notify_on_comment"] is True
    assert data["notify_on_reply"] is True
    assert data["notify_on_vote_milestone"] is True
    assert data["notify_on_announcements"] is True
    assert data["notify_timeline_reminders"] is True
    assert data["push_enabled"] is True
    assert "created_at" in data
    assert "updated_at" in data

    # Proves lazy creation landed in DB
    assert NotificationPreference.objects.filter(user=user).exists()


def test_repeat_get_preferences_returns_same_row(auth_api):
    client, user = auth_api()
    res1 = client.get("/api/v1/notifications/preferences/")
    pref = NotificationPreference.objects.get(user=user)

    res2 = client.get("/api/v1/notifications/preferences/")
    assert res1.json()["created_at"] == res2.json()["created_at"]
    assert NotificationPreference.objects.filter(user=user).count() == 1
    assert pref.id == NotificationPreference.objects.get(user=user).id


def test_patch_single_preference_flag(auth_api):
    client, user = auth_api()
    response = client.patch(
        "/api/v1/notifications/preferences/",
        {"notify_on_comment": False},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["notify_on_comment"] is False
    assert data["notify_on_reply"] is True
    assert data["push_enabled"] is True

    pref = NotificationPreference.objects.get(user=user)
    assert pref.notify_on_comment is False
    assert pref.notify_on_reply is True


def test_patch_all_preference_flags(auth_api):
    client, user = auth_api()
    all_false = {
        "notify_on_comment": False,
        "notify_on_reply": False,
        "notify_on_vote_milestone": False,
        "notify_on_announcements": False,
        "notify_timeline_reminders": False,
        "push_enabled": False,
    }
    response = client.patch(
        "/api/v1/notifications/preferences/",
        all_false,
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    for k, v in all_false.items():
        assert data[k] is v


def test_patch_non_boolean_value_returns_400(auth_api):
    client, user = auth_api()
    response = client.patch(
        "/api/v1/notifications/preferences/",
        {"push_enabled": "not_a_bool"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_patch_ignores_unknown_keys(auth_api):
    client, user = auth_api()
    response = client.patch(
        "/api/v1/notifications/preferences/",
        {"unrecognized_admin_key": "some_value", "notify_on_reply": False},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["notify_on_reply"] is False
    assert "unrecognized_admin_key" not in response.json()


def test_preferences_unverified_returns_403(auth_api):
    client, user = auth_api(is_verified=False)
    assert client.get("/api/v1/notifications/preferences/").status_code == status.HTTP_403_FORBIDDEN
    assert (
        client.patch(
            "/api/v1/notifications/preferences/",
            {"push_enabled": False},
            format="json",
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )


def test_preferences_response_shape_has_no_sensitive_fields(auth_api):
    client, user = auth_api()
    response = client.get("/api/v1/notifications/preferences/")
    data = response.json()
    expected_keys = {
        "notify_on_comment",
        "notify_on_reply",
        "notify_on_vote_milestone",
        "notify_on_announcements",
        "notify_timeline_reminders",
        "push_enabled",
        "created_at",
        "updated_at",
    }
    assert set(data.keys()) == expected_keys
    for sensitive in ("id", "user", "user_id", "email", "fcm_token"):
        assert sensitive not in data
