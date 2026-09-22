"""Tests for Notification API endpoints (Phase 6.2 — 07 §11.1–§11.3, D5, R4, R6)."""

from __future__ import annotations

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status

from apps.notifications.models import Notification


def test_list_notifications_shape_matches_spec_contract(auth_api, make_post, make_comment):
    client, user = auth_api()
    post = make_post(author=user, title="Post Title")
    comment = make_comment(post=post, author=user, body="Comment body")

    notif = Notification.objects.create(
        recipient=user,
        type=Notification.NotificationType.COMMENT,
        title="New Comment",
        message="Someone commented",
        post=post,
        comment=comment,
    )

    response = client.get("/api/v1/notifications/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert set(data.keys()) == {"count", "unread_count", "next", "previous", "results"}
    assert data["count"] == 1
    assert data["unread_count"] == 1

    item = data["results"][0]
    expected_keys = {
        "id",
        "type",
        "title",
        "message",
        "is_read",
        "read_at",
        "post_id",
        "comment_id",
        "created_at",
    }
    assert set(item.keys()) == expected_keys
    assert item["id"] == str(notif.id)
    assert item["post_id"] == str(post.id)
    assert item["comment_id"] == str(comment.id)
    assert item["is_read"] is False
    assert item["read_at"] is None


def test_list_notifications_filter_is_read_false(auth_api, make_notification):
    client, user = auth_api()
    n1 = make_notification(recipient=user, is_read=False)
    n2 = make_notification(recipient=user, is_read=False)
    make_notification(recipient=user, is_read=True, read_at=timezone.now())

    response = client.get("/api/v1/notifications/?is_read=false")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] == 2
    returned_ids = {r["id"] for r in data["results"]}
    assert returned_ids == {str(n1.id), str(n2.id)}


def test_list_notifications_filter_is_read_true(auth_api, make_notification):
    client, user = auth_api()
    make_notification(recipient=user, is_read=False)
    n_read = make_notification(recipient=user, is_read=True, read_at=timezone.now())

    response = client.get("/api/v1/notifications/?is_read=true")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == str(n_read.id)


def test_list_notifications_invalid_is_read_returns_400_envelope(auth_api):
    client, user = auth_api()
    response = client.get("/api/v1/notifications/?is_read=maybe")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": {
            "code": "invalid_is_read",
            "message": "The 'is_read' filter must be 'true' or 'false'.",
        }
    }


def test_list_notifications_ordered_by_created_at_desc(auth_api, make_notification):
    client, user = auth_api()
    n1 = make_notification(recipient=user, title="First")
    n2 = make_notification(recipient=user, title="Second")

    response = client.get("/api/v1/notifications/")
    assert response.status_code == status.HTTP_200_OK
    results = response.json()["results"]
    assert results[0]["id"] == str(n2.id)
    assert results[1]["id"] == str(n1.id)


def test_list_notifications_is_owner_scoped(auth_api, make_notification):
    client_a, user_a = auth_api("notif_a@example.com")
    client_b, user_b = auth_api("notif_b@example.com")
    make_notification(recipient=user_a)

    response = client_b.get("/api/v1/notifications/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] == 0
    assert response.json()["unread_count"] == 0


def test_list_notifications_unread_count_accurate(auth_api, make_notification):
    client, user = auth_api()
    make_notification(recipient=user, is_read=False)
    make_notification(recipient=user, is_read=False)
    make_notification(recipient=user, is_read=True, read_at=timezone.now())

    response = client.get("/api/v1/notifications/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] == 3
    assert data["unread_count"] == 2


def test_mark_read_own_notification_returns_200(auth_api, make_notification):
    client, user = auth_api()
    notif = make_notification(recipient=user, is_read=False)

    response = client.post(f"/api/v1/notifications/{notif.id}/read/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(notif.id)
    assert data["is_read"] is True
    assert data["read_at"] is not None

    notif.refresh_from_db()
    assert notif.is_read is True
    assert notif.read_at is not None


def test_mark_read_already_read_notification_is_idempotent(auth_api, make_notification):
    client, user = auth_api()
    initial_read_at = timezone.now()
    notif = make_notification(recipient=user, is_read=True, read_at=initial_read_at)

    response = client.post(f"/api/v1/notifications/{notif.id}/read/")
    assert response.status_code == status.HTTP_200_OK

    notif.refresh_from_db()
    assert notif.is_read is True
    # 6.1 R4: read_at is preserved, not overwritten
    assert notif.read_at == initial_read_at


def test_mark_read_foreign_notification_returns_404_envelope(auth_api, make_notification):
    client_a, user_a = auth_api("owner_notif@example.com")
    client_b, user_b = auth_api("attacker_notif@example.com")
    notif = make_notification(recipient=user_a, is_read=False)

    response = client_b.post(f"/api/v1/notifications/{notif.id}/read/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "error": {
            "code": "notification_not_found",
            "message": "Notification not found.",
        }
    }


def test_mark_read_malformed_uuid_returns_404_envelope(auth_api):
    client, user = auth_api()
    response = client.post("/api/v1/notifications/malformed-uuid-value/read/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "error": {
            "code": "notification_not_found",
            "message": "Notification not found.",
        }
    }


def test_read_all_marks_all_unread_in_single_update_query(auth_api, make_notification):
    client, user = auth_api()
    for _ in range(4):
        make_notification(recipient=user, is_read=False)

    with CaptureQueriesContext(connection) as queries:
        response = client.post("/api/v1/notifications/read-all/")
        assert response.status_code == status.HTTP_200_OK

    assert response.json() == {
        "updated_count": 4,
        "message": "All unread notifications marked as read.",
    }

    # Verify single UPDATE query naming both is_read and read_at (D5)
    update_queries = [q["sql"] for q in queries if q["sql"].strip().upper().startswith("UPDATE")]
    assert len(update_queries) == 1
    update_sql = update_queries[0]
    assert "is_read" in update_sql
    assert "read_at" in update_sql


def test_read_all_zero_unread_returns_zero_updated_count(auth_api, make_notification):
    client, user = auth_api()
    make_notification(recipient=user, is_read=True, read_at=timezone.now())

    response = client.post("/api/v1/notifications/read-all/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["updated_count"] == 0


def test_unread_count_decrements_after_mark_read_and_read_all(auth_api, make_notification):
    client, user = auth_api()
    n1 = make_notification(recipient=user, is_read=False)
    make_notification(recipient=user, is_read=False)

    # Initial count: 2
    res1 = client.get("/api/v1/notifications/")
    assert res1.json()["unread_count"] == 2

    # Mark 1 read: drops to 1
    client.post(f"/api/v1/notifications/{n1.id}/read/")
    res2 = client.get("/api/v1/notifications/")
    assert res2.json()["unread_count"] == 1

    # Read-all: drops to 0
    client.post("/api/v1/notifications/read-all/")
    res3 = client.get("/api/v1/notifications/")
    assert res3.json()["unread_count"] == 0
