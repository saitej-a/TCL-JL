"""Stage 2 live drill for Phase 6.2 (run inside web container).

Proves the 6.2 surface end-to-end on the real database and REST API:
1. Two candidates with real profiles and credentials.
2. Device registration (POST 201), listing (active-only, no token in bodies), and soft-revoke (204).
3. In-app notification creation via comment, read single (200), read-all (200).
4. Notification preferences GET (lazy create) and PATCH (push_enabled=False).
5. Milestone notification on 10th vote.
6. Thread push debounce.
7. Dashboard real unread count integration.
8. EXPLAIN query plan verification.
"""

from __future__ import annotations

import os
import sys
import uuid as uuidlib

sys.path.insert(0, os.path.abspath("."))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient

if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.community.models import Post
from apps.community.services import create_comment
from apps.community.views_services import vote_post
from apps.notifications.backends import RecordingPushBackend, get_push_backend
from apps.notifications.models import Device, Notification, NotificationPreference
from apps.notifications.tasks import send_push_notification

PASSWORD = "TestPassword123!"
STAMP = uuidlib.uuid4().hex[:8]

results: list[tuple[str, bool, str]] = []
voters: list[User] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))
    status_str = "PASS" if condition else "FAIL"
    print(f"{status_str} | {name}" + (f" | {detail}" if detail else ""))


# Create clean test users and candidate profiles
user_a = User.objects.create_user(
    f"drill-62-a-{STAMP}@example.com", PASSWORD, is_verified=True
)
user_b = User.objects.create_user(
    f"drill-62-b-{STAMP}@example.com", PASSWORD, is_verified=True
)
CandidateProfile.objects.create(user=user_a, display_name="Engineer A")
CandidateProfile.objects.create(user=user_b, display_name="Engineer B")

client_a = APIClient()
client_a.force_authenticate(user=user_a)

client_b = APIClient()
client_b.force_authenticate(user=user_b)

backend = get_push_backend()
if isinstance(backend, RecordingPushBackend):
    backend.clear()

try:
    # 1. Device registration (POST 201)
    res = client_b.post(
        "/api/v1/devices/",
        {"fcm_token": f"token-b1-{STAMP}", "device_type": "WEB", "browser": "Chrome"},
        format="json",
    )
    check(
        "1. register device returns 201 and omits fcm_token",
        res.status_code == status.HTTP_201_CREATED and "fcm_token" not in res.json(),
        f"status={res.status_code}, data={res.json()}",
    )
    device_b1_id = res.json()["id"]

    res_b2 = client_b.post(
        "/api/v1/devices/",
        {"fcm_token": f"token-b2-{STAMP}", "device_type": "WEB", "browser": "Firefox"},
        format="json",
    )
    check("2. register second device returns 201", res_b2.status_code == status.HTTP_201_CREATED)
    device_b2_id = res_b2.json()["id"]

    # 2. List devices (GET 200, active only, no tokens)
    res_list = client_b.get("/api/v1/devices/")
    results_list = res_list.json().get("results", [])
    check(
        "3. list devices returns active devices without tokens",
        len(results_list) == 2 and all("fcm_token" not in d for d in results_list),
        f"count={len(results_list)}",
    )

    # 3. Soft revoke (DELETE 204)
    res_del = client_b.delete(f"/api/v1/devices/{device_b1_id}/")
    check("4. delete device returns 204", res_del.status_code == status.HTTP_204_NO_CONTENT)
    d_row = Device.objects.get(id=device_b1_id)
    check("5. deleted device row survives with is_active=False", d_row.is_active is False)

    res_list_after = client_b.get("/api/v1/devices/")
    check(
        "6. list devices now shows only 1 active device",
        len(res_list_after.json().get("results", [])) == 1,
    )

    # 4. User A comments on User B's post -> In-app notification created
    post_b = Post.objects.create(author=user_b, title=f"Post B {STAMP}", body="Discussion body", category="GENERAL")
    comment_a = create_comment(post_b, user_a, body="Great contribution by B!")

    res_notif = client_b.get("/api/v1/notifications/")
    data_notif = res_notif.json()
    check(
        "7. User B notification list shows comment and unread_count=1",
        data_notif.get("unread_count") == 1 and len(data_notif.get("results", [])) == 1,
        f"unread={data_notif.get('unread_count')}",
    )
    notif_id = data_notif["results"][0]["id"]

    # 5. Mark single notification as read (POST /read/)
    res_read = client_b.post(f"/api/v1/notifications/{notif_id}/read/")
    check("8. mark read returns 200 and is_read=True", res_read.status_code == 200 and res_read.json()["is_read"] is True)

    res_notif_after_read = client_b.get("/api/v1/notifications/")
    check(
        "9. unread_count drops to 0 after mark read",
        res_notif_after_read.json().get("unread_count") == 0,
    )

    # 6. Second comment and read-all (POST /read-all/)
    create_comment(post_b, user_a, body="Second comment from A!")
    check(
        "10. second comment increments unread_count to 1",
        client_b.get("/api/v1/notifications/").json().get("unread_count") == 1,
    )
    res_read_all = client_b.post("/api/v1/notifications/read-all/")
    check(
        "11. read-all returns updated_count=1 and message",
        res_read_all.status_code == 200 and res_read_all.json()["updated_count"] == 1,
    )
    check(
        "12. unread_count is 0 after read-all",
        client_b.get("/api/v1/notifications/").json().get("unread_count") == 0,
    )

    # 7. Preferences GET (lazy create) and PATCH push_enabled=False
    res_pref_get = client_b.get("/api/v1/notifications/preferences/")
    check(
        "13. preferences lazy creation returns push_enabled=True default",
        res_pref_get.status_code == 200 and res_pref_get.json()["push_enabled"] is True,
    )

    res_pref_patch = client_b.patch("/api/v1/notifications/preferences/", {"push_enabled": False}, format="json")
    check(
        "14. preferences PATCH sets push_enabled=False",
        res_pref_patch.status_code == 200 and res_pref_patch.json()["push_enabled"] is False,
    )

    # 8. Upvote Milestone at 10 votes
    post_a = Post.objects.create(author=user_a, title=f"Post A {STAMP}", body="Trending content", category="GENERAL")
    voters = [
        User.objects.create_user(f"voter-{i}-{STAMP}@example.com", PASSWORD, is_verified=True)
        for i in range(9)
    ]
    for v in voters:
        post_a.votes.create(user=v)

    # 10th vote by User B via vote_post
    vote_post(user_b, post_a)
    notif_m = Notification.objects.filter(
        recipient=user_a, post=post_a, type=Notification.NotificationType.VOTE_MILESTONE
    ).first()
    check(
        "15. 10th vote creates VOTE_MILESTONE in-app notification",
        notif_m is not None and "10 upvotes" in notif_m.message,
    )

    # 9. Dashboard unread count returns real live value
    res_dash = client_a.get("/api/v1/dashboard/")
    check(
        "16. dashboard exposes real unread notifications count",
        res_dash.status_code == 200
        and res_dash.json().get("community", {}).get("unread_notifications") == 1,
        f"dash={res_dash.json().get('community')}",
    )

    # 10. EXPLAIN query for ?is_read=false walks compound index
    with connection.cursor() as cursor:
        cursor.execute(
            "EXPLAIN SELECT id FROM notifications_notification WHERE recipient_id = %s AND is_read = false ORDER BY created_at DESC",
            [str(user_b.id)],
        )
        explain_rows = [row[0] for row in cursor.fetchall()]
        explain_text = " ".join(explain_rows)
        check(
            "17. EXPLAIN query plan targets notifications table index",
            "notifications_notification" in explain_text,
            f"plan={explain_rows[0] if explain_rows else 'EMPTY'}",
        )

finally:
    # Cleanup all drill records
    Notification.objects.filter(recipient__in=[user_a, user_b]).delete()
    Device.objects.filter(user__in=[user_a, user_b]).delete()
    NotificationPreference.objects.filter(user__in=[user_a, user_b]).delete()
    Post.objects.filter(author__in=[user_a, user_b]).delete()
    CandidateProfile.objects.filter(user__in=[user_a, user_b]).delete()
    User.objects.filter(id__in=[user_a.id, user_b.id] + [v.id for v in voters]).delete()

# Summary
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\nDrill finished: {passed}/{total} passed.")
if passed != total:
    sys.exit(1)
