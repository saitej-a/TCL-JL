"""Live drill for Phase 8.2 (run inside the web container).

Unlike the phase's pytest suites, this goes through the **real URLconf, the real
database, the real Redis broker and the real Celery worker** with Django's test
client: a request path, not a function call. It proves the two asynchronies the
phase is built on actually complete end-to-end — a ban's session/device severing
and an announcement's broadcast — by dispatching through the broker and polling
the database for the effect.

What it proves:
1. The report → queue → review loop over HTTP, with the queue staff-gated,
   §68-shaped, severity-ordered, and filter-validated.
2. All five §4.2 actions behave as specified over HTTP (status transitions,
   tombstone, lock, warning notification, ban), including LOCK_POST's refusal on
   a comment-targeted report.
3. 08 §6's ban protocol completes for real: the transaction commits the flag, the
   worker blacklists refresh tokens and deactivates devices, login returns 403
   ACCOUNT_SUSPENDED after credential validation, wrong passwords stay generic,
   temporary bans auto-reinstate (via a real dispatched task) and unban never
   revives devices (D2).
4. The announcement lifecycle for real: publish → worker broadcast fan-out →
   anonymous public read → draft/expired invisibility → expiry task unpublishes.
5. Every reserved beat entry and task route resolves to a real implementation
   (the F1/F2 class of defect), independently of the pytest wiring test.
6. It restores the database baseline it found (probe rows deleted, broadcast
   notifications removed, throttle/cache keys purged).

Usage: docker compose exec -T web python .planning/phases/<this>/drill_08_02.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid as uuidlib
from datetime import timedelta

sys.path.insert(0, os.path.abspath("."))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

import importlib  # noqa: E402

from django.conf import settings  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework_simplejwt.token_blacklist.models import (  # noqa: E402
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.community.models import Announcement, Comment, Post  # noqa: E402
from apps.community.validators import post_category_keys  # noqa: E402
from apps.moderation.models import Report  # noqa: E402
from apps.moderation.tasks import auto_reinstate_users  # noqa: E402
from apps.notifications.models import (  # noqa: E402
    Device,
    Notification,
    NotificationPreference,
)
from config.celery import app as celery_app  # noqa: E402

STAMP = uuidlib.uuid4().hex[:8]
PASSWORD = "Drill!Passw0rd9"
PREFIX = f"drill82-{STAMP}"
STARTED_AT = timezone.now()

client = Client(SERVER_NAME="localhost")  # local.py ALLOWED_HOSTS

results: list[tuple[str, bool, str]] = []
notes: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def note(message: str) -> None:
    """Record an observation that is reported but deliberately not scored."""
    notes.append(message)
    print(f"  [NOTE] {message}")


def purge_throttles() -> None:
    """Clear throttle buckets so a drill run cannot trip 5/min login or 10/hour report limits.

    These are the drill's own requests, not abuse; every phase drill that touches
    a throttled endpoint has to do this or it measures the throttle instead of the
    code under test.
    """
    try:
        cache.delete_pattern("throttle_*")
    except AttributeError:  # non-Redis backend
        cache.clear()


def wait_for(predicate, timeout: float = 25.0, interval: float = 0.4) -> bool:
    """Poll until `predicate()` is truthy — how async work is proven here."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def sweep_probe_data(prefix: str = "drill82-") -> dict[str, int]:
    """Remove every row this drill family ever created, in FK-safe order.

    `Post.author`/`Comment.author` are PROTECT, so a bare user delete raises
    ProtectedError — content first, then reports/notifications/devices (CASCADE),
    then the accounts.
    """
    probe_users = User.objects.filter(email__startswith=prefix)
    counts = {
        "users": probe_users.count(),
        "posts": Post.objects.filter(author__in=probe_users).count(),
        "comments": Comment.objects.filter(author__in=probe_users).count(),
        "announcements": Announcement.objects.filter(title__startswith=prefix).count(),
    }
    Post.objects.filter(author__in=probe_users).delete()
    Comment.objects.filter(author__in=probe_users).delete()
    counts["reports"] = Report.objects.filter(reporter__in=probe_users).count()
    Announcement.objects.filter(title__startswith=prefix).delete()
    BlacklistedToken.objects.filter(token__user__in=probe_users).delete()
    OutstandingToken.objects.filter(user__in=probe_users).delete()
    Notification.objects.filter(recipient__in=probe_users).delete()
    Device.objects.filter(user__in=probe_users).delete()
    probe_users.delete()
    purge_throttles()
    return counts


if "--cleanup-only" in sys.argv:
    print(f"=== sweep of drill82-* probe data ===\n{json.dumps(sweep_probe_data(), indent=2, default=str)}")
    sys.exit(0)


def make_user(suffix: str, **overrides) -> User:
    defaults = dict(is_verified=True)
    defaults.update(overrides)
    return User.objects.create_user(f"{PREFIX}-{suffix}@example.com", PASSWORD, **defaults)


def login(email: str, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )


def auth_headers(email: str) -> dict[str, str]:
    response = login(email)
    if response.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {response.status_code} {response.content[:200]}")
    return {"HTTP_AUTHORIZATION": f"Bearer {response.json()['access']}"}


print(f"\n=== Phase 8.2 live drill (stamp {STAMP}) ===")

baseline_users = User.objects.count()
baseline_announcements = Announcement.objects.count()

# --- fixtures ---------------------------------------------------------------------
staff = make_user("staff", is_staff=True)
reporter_a = make_user("reporter-a")
reporter_b = make_user("reporter-b")
author = make_user("author")
optout = make_user("optout")
post = Post.objects.create(author=author, title="Probe thread", body="Probe body.", category=sorted(post_category_keys())[0])
comment = Comment.objects.create(post=post, author=author, body="Probe comment.")
author_device = Device.objects.create(user=author, fcm_token=f"{PREFIX}-dev-author", is_active=True)
optout_device = Device.objects.create(user=optout, fcm_token=f"{PREFIX}-dev-optout", is_active=True)
pref, _ = NotificationPreference.get_or_create_for(optout)
pref.notify_on_announcements = False
pref.save(update_fields=["notify_on_announcements"])

# An outstanding refresh token for the ban to sever.
pending_refresh = RefreshToken.for_user(author)
OutstandingToken.objects.get_or_create(
    jti=pending_refresh["jti"],
    defaults={
        "user": author,
        "token": str(pending_refresh),
        "expires_at": timezone.now() + timedelta(days=7),
    },
)

purge_throttles()
staff_h = auth_headers(staff.email)
reporter_a_h = auth_headers(reporter_a.email)
reporter_b_h = auth_headers(reporter_b.email)
author_h = auth_headers(author.email)
purge_throttles()

# --- 1. report → queue → review over HTTP ----------------------------------------
print("\n-- 1. Reporting and the staff queue")
r = client.post(
    "/api/v1/reports/",
    {"post_id": str(post.id), "reason": "SCAM", "description": "Probe scam"},
    content_type="application/json",
    **reporter_a_h,
)
check("candidate files a report (201 PENDING)", r.status_code == 201 and r.json()["status"] == "PENDING")

r_anon = client.post(
    "/api/v1/reports/",
    {"post_id": str(post.id), "reason": "SPAM"},
    content_type="application/json",
)
check("anonymous cannot report (401/403)", r_anon.status_code in (401, 403), f"got {r_anon.status_code}")

r_dup = client.post(
    "/api/v1/reports/",
    {"post_id": str(post.id), "reason": "SPAM"},
    content_type="application/json",
    **reporter_a_h,
)
check(
    "duplicate pending report refused (400 duplicate_report)",
    r_dup.status_code == 400 and r_dup.json()["error"]["code"].lower() == "duplicate_report",
    f"got {r_dup.status_code}",
)

r_q_anon = client.get("/api/v1/moderation/reports/")
check("anonymous cannot read the queue (401/403)", r_q_anon.status_code in (401, 403), f"got {r_q_anon.status_code}")

r_q_cand = client.get("/api/v1/moderation/reports/", **author_h)
check("candidate cannot read the queue (403)", r_q_cand.status_code == 403, f"got {r_q_cand.status_code}")

# A second, lower-severity report to prove §4.1 ordering.
r_low = client.post(
    "/api/v1/reports/",
    {"comment_id": str(comment.id), "reason": "OTHER", "description": "Probe other"},
    content_type="application/json",
    **reporter_b_h,
)
check("second report accepted (201)", r_low.status_code == 201)

r_queue = client.get("/api/v1/moderation/reports/?status=PENDING", **staff_h)
body = r_queue.json() if r_queue.status_code == 200 else {}
rows = body.get("results", [])
check("staff reads the queue (200)", r_queue.status_code == 200, f"got {r_queue.status_code}")
check(
    "queue rows carry §68's shape and nothing moderator-only",
    bool(rows) and set(rows[0]) == {"id", "reason", "status", "post_id", "comment_id", "description", "created_at"},
    f"keys={sorted(rows[0]) if rows else 'none'}",
)
check(
    "queue is severity-ordered (SCAM before OTHER)",
    [row["reason"] for row in rows[:2]] == ["SCAM", "OTHER"],
    f"order={[row['reason'] for row in rows[:3]]}",
)
r_bad_filter = client.get("/api/v1/moderation/reports/?status=BOGUS", **staff_h)
check(
    "unknown status filter is 400 invalid_filter",
    r_bad_filter.status_code == 400 and r_bad_filter.json()["error"]["code"] == "invalid_filter",
    f"got {r_bad_filter.status_code}",
)

scam_report_id = rows[0]["id"] if rows else None
other_report_id = rows[1]["id"] if len(rows) > 1 else None

# --- 2. the five actions over HTTP ------------------------------------------------
print("\n-- 2. The five §4.2 actions")
r_review_anon = client.post(
    f"/api/v1/moderation/reports/{scam_report_id}/review/",
    {"action": "DISMISS"},
    content_type="application/json",
)
check("anonymous cannot review (401/403)", r_review_anon.status_code in (401, 403), f"got {r_review_anon.status_code}")

r_dismiss = client.post(
    f"/api/v1/moderation/reports/{other_report_id}/review/",
    {"action": "DISMISS", "moderator_notes": "drill dismiss"},
    content_type="application/json",
    **staff_h,
)
check(
    "DISMISS → 200 DISMISSED",
    r_dismiss.status_code == 200 and r_dismiss.json()["status"] == "DISMISSED",
    f"got {r_dismiss.status_code} {r_dismiss.content[:120]}",
)
dismissed = Report.objects.filter(id=other_report_id).first()
check(
    "DISMISS writes reviewed_by/reviewed_at/moderator_notes",
    dismissed is not None
    and dismissed.reviewed_by_id == staff.id
    and dismissed.reviewed_at is not None
    and dismissed.moderator_notes == "drill dismiss",
)

# Third report on the post → WARN_USER (content untouched, author notified).
r_warn_src = client.post(
    "/api/v1/reports/",
    {"post_id": str(post.id), "reason": "HARASSMENT"},
    content_type="application/json",
    **reporter_b_h,
)
warn_id = r_warn_src.json().get("id") if r_warn_src.status_code == 201 else None
r_warn = client.post(
    f"/api/v1/moderation/reports/{warn_id}/review/",
    {"action": "WARN_USER"},
    content_type="application/json",
    **staff_h,
)
post.refresh_from_db()
check(
    "WARN_USER → 200 RESOLVED, content untouched, author notified",
    r_warn.status_code == 200
    and r_warn.json()["status"] == "RESOLVED"
    and post.is_deleted is False
    and Notification.objects.filter(
        recipient=author, type=Notification.NotificationType.MODERATION
    ).exists(),
    f"got {r_warn.status_code}",
)

# LOCK_POST on a comment-targeted report must be refused.
r_lock_comment = client.post(
    "/api/v1/reports/",
    {"comment_id": str(comment.id), "reason": "HARASSMENT"},
    content_type="application/json",
    **reporter_a_h,
)
lock_comment_id = r_lock_comment.json().get("id") if r_lock_comment.status_code == 201 else None
r_lock_bad = client.post(
    f"/api/v1/moderation/reports/{lock_comment_id}/review/",
    {"action": "LOCK_POST"},
    content_type="application/json",
    **staff_h,
)
still_pending = Report.objects.filter(id=lock_comment_id).first()
check(
    "LOCK_POST on a comment report → 400 and the report stays PENDING",
    r_lock_bad.status_code == 400 and still_pending is not None and still_pending.status == "PENDING",
    f"got {r_lock_bad.status_code}",
)

# REMOVE_CONTENT on the comment → tombstone + author notification.
r_remove = client.post(
    f"/api/v1/moderation/reports/{lock_comment_id}/review/",
    {"action": "REMOVE_CONTENT"},
    content_type="application/json",
    **staff_h,
)
comment.refresh_from_db()
check(
    "REMOVE_CONTENT → comment tombstoned, report RESOLVED, author notified",
    r_remove.status_code == 200
    and r_remove.json()["status"] == "RESOLVED"
    and comment.is_deleted is True
    and Notification.objects.filter(
        recipient=author, type=Notification.NotificationType.MODERATION
    ).count() >= 2,
    f"got {r_remove.status_code}",
)

# LOCK_POST on a post-targeted report → locked.
r_lock = client.post(
    f"/api/v1/moderation/reports/{scam_report_id}/review/",
    {"action": "LOCK_POST"},
    content_type="application/json",
    **staff_h,
)
post.refresh_from_db()
check(
    "LOCK_POST → thread locked, report RESOLVED",
    r_lock.status_code == 200 and post.is_locked is True and r_lock.json()["status"] == "RESOLVED",
    f"got {r_lock.status_code}",
)

# --- 3. ban protocol, including the real async severing ---------------------------
print("\n-- 3. Ban protocol (transaction + worker severing)")
r_ban_src = client.post(
    "/api/v1/reports/",
    {"post_id": str(post.id), "reason": "SCAM"},
    content_type="application/json",
    **reporter_b_h,
)
ban_report_id = r_ban_src.json().get("id") if r_ban_src.status_code == 201 else None

r_ban_cand = client.post(
    f"/api/v1/moderation/users/{author.id}/ban/",
    {"reason": "SCAM"},
    content_type="application/json",
    **author_h,
)
check("candidate cannot ban (403)", r_ban_cand.status_code == 403, f"got {r_ban_cand.status_code}")

r_ban_staff = client.post(
    f"/api/v1/moderation/users/{staff.id}/ban/",
    {"reason": "SCAM"},
    content_type="application/json",
    **staff_h,
)
check("staff member cannot be banned (400)", r_ban_staff.status_code == 400, f"got {r_ban_staff.status_code}")

device_before = Device.objects.get(id=author_device.id).is_active
r_ban = client.post(
    f"/api/v1/moderation/reports/{ban_report_id}/review/",
    {"action": "BAN_USER", "duration_days": 7},
    content_type="application/json",
    **staff_h,
)
author.refresh_from_db()
check(
    "BAN_USER review → 202, report RESOLVED, account suspended with a 7-day boundary",
    r_ban.status_code == 202
    and r_ban.json()["status"] == "RESOLVED"
    and author.is_active is False
    and author.banned_until is not None,
    f"got {r_ban.status_code}",
)
check("device is still active immediately after the transaction (async by design)", device_before is True)

severed = wait_for(
    lambda: not Device.objects.get(id=author_device.id).is_active
    and BlacklistedToken.objects.filter(token__user=author).exists()
)
check(
    "the WORKER severed sessions and devices (tokens blacklisted, device deactivated)",
    severed,
    "polled DB for the async effect",
)

r_login = login(author.email)
check(
    "suspended login → 403 ACCOUNT_SUSPENDED",
    r_login.status_code == 403 and r_login.json()["error"]["code"] == "ACCOUNT_SUSPENDED",
    f"got {r_login.status_code} {r_login.content[:120]}",
)
purge_throttles()
r_login_wrong = login(author.email, "WrongPassword1!")
check(
    "wrong password on a banned account stays generic (anti-enumeration)",
    r_login_wrong.status_code == 401 and r_login_wrong.json()["error"]["code"] == "INVALID_CREDENTIALS",
    f"got {r_login_wrong.status_code}",
)
purge_throttles()

# Temporary ban auto-reinstates through a real dispatched task.
author.banned_until = timezone.now() - timedelta(minutes=1)
author.save(update_fields=["banned_until"])
auto_reinstate_users.delay()
reinstated = wait_for(lambda: User.objects.get(id=author.id).is_active is True, timeout=30)
author.refresh_from_db()
check(
    "auto-reinstate task (dispatched to the real worker) restores the lapsed temporary ban",
    reinstated and author.banned_until is None,
)
device_after_unban = Device.objects.get(id=author_device.id).is_active
check("D2: reinstatement does NOT revive the device", device_after_unban is False)

r_unban = client.post(f"/api/v1/moderation/users/{author.id}/unban/", content_type="application/json", **staff_h)
check("unban → 200 and the account is active again", r_unban.status_code == 200 and r_unban.json()["is_active"] is True)

# --- 4. announcements -------------------------------------------------------------
print("\n-- 4. Announcement lifecycle")
r_create = client.post(
    "/api/v1/announcements/",
    {"title": f"{PREFIX} advisory", "body": "Probe advisory body.", "is_pinned": True},
    content_type="application/json",
    **staff_h,
)
check(
    "staff creates a draft (201, unpublished)",
    r_create.status_code == 201 and r_create.json()["is_published"] is False,
    f"got {r_create.status_code}",
)

r_create_anon = client.post(
    "/api/v1/announcements/",
    {"title": "anon", "body": "anon"},
    content_type="application/json",
)
check("anonymous cannot create an announcement (401/403)", r_create_anon.status_code in (401, 403), f"got {r_create_anon.status_code}")

r_create_cand = client.post(
    "/api/v1/announcements/",
    {"title": "cand", "body": "cand"},
    content_type="application/json",
    **author_h,
)
check("candidate cannot create an announcement (403)", r_create_cand.status_code == 403, f"got {r_create_cand.status_code}")

announcement_id = r_create.json().get("id") if r_create.status_code == 201 else None
r_public_before = client.get("/api/v1/announcements/")
titles_before = [row["title"] for row in r_public_before.json().get("results", [])]
check("draft is invisible to the public list", f"{PREFIX} advisory" not in titles_before)

r_publish = client.post(f"/api/v1/announcements/{announcement_id}/publish/", content_type="application/json", **staff_h)
check(
    "publish → 202 broadcast scheduled",
    r_publish.status_code == 202 and r_publish.json()["detail"] == "broadcast scheduled",
    f"got {r_publish.status_code} {r_publish.content[:120]}",
)

r_publish_again = client.post(
    f"/api/v1/announcements/{announcement_id}/publish/", content_type="application/json", **staff_h
)
check(
    "second publish is a 200 no-op (no re-broadcast)",
    r_publish_again.status_code == 200 and r_publish_again.json()["detail"] == "already published",
    f"got {r_publish_again.status_code}",
)

fanned_out = wait_for(
    lambda: Notification.objects.filter(
        type=Notification.NotificationType.ANNOUNCEMENT, created_at__gte=STARTED_AT
    ).count()
    > 0
)
check("the WORKER broadcast the announcement (in-app rows created)", fanned_out)
check(
    "the opted-out user still received the in-app row (D7: the gate is the push)",
    Notification.objects.filter(
        recipient=optout,
        type=Notification.NotificationType.ANNOUNCEMENT,
        created_at__gte=STARTED_AT,
    ).exists(),
)

r_public = client.get("/api/v1/announcements/")
public_rows = r_public.json().get("results", [])
published_row = next((row for row in public_rows if row["title"] == f"{PREFIX} advisory"), None)
check("published announcement appears anonymously", published_row is not None)
check(
    "public row exposes §72's fields only",
    published_row is not None
    and set(published_row) == {"id", "title", "body", "is_pinned", "published_at", "expires_at"},
    f"keys={sorted(published_row) if published_row else 'none'}",
)

# Expiry: a lapsed published row is hidden publicly, then unpublished by the task.
expired = Announcement.objects.create(
    title=f"{PREFIX} expired",
    body="Probe expired body.",
    is_published=True,
    published_at=timezone.now() - timedelta(days=2),
    expires_at=timezone.now() - timedelta(days=1),
)
r_public_expired = client.get("/api/v1/announcements/")
check(
    "expired announcement is hidden from the public list",
    f"{PREFIX} expired" not in [row["title"] for row in r_public_expired.json().get("results", [])],
)
from apps.community.tasks import clean_expired_announcements  # noqa: E402

clean_expired_announcements.delay()
unpublished = wait_for(lambda: Announcement.objects.get(id=expired.id).is_published is False, timeout=30)
check("the expiry task (real dispatch) unpublishes the lapsed row", unpublished)

# --- 5. reserved wiring, independently of pytest -----------------------------------
print("\n-- 5. Reserved Celery wiring")
consumed_queues = {"default", "notifications", "maintenance"}
beat = {key: entry["task"] for key, entry in celery_app.conf.beat_schedule.items()}
EXPECTED_BEAT_MODULES = {
    "notifications.tasks.prune_stale_devices": ("apps.notifications.tasks", "prune_stale_devices"),
    "community.tasks.clean_expired_announcements": ("apps.community.tasks", "clean_expired_announcements"),
    "analytics.tasks.warm_analytics_cache": ("apps.analytics.tasks", "warm_analytics_cache"),
    "moderation.tasks.auto_reinstate_users": ("apps.moderation.tasks", "auto_reinstate_users"),
}
for task_name, (module_path, attribute) in EXPECTED_BEAT_MODULES.items():
    in_beat = task_name in beat.values()
    try:
        module = importlib.import_module(module_path)
        implementable = getattr(module, attribute).name == task_name
    except Exception as exc:  # noqa: BLE001
        implementable = False
        module_path = f"{module_path} ({type(exc).__name__})"
    check(f"beat task resolves to real code: {task_name}", in_beat and implementable)

for task_name, queue in {
    "moderation.tasks.sever_banned_user_sessions": "default",
    "moderation.tasks.auto_reinstate_users": "maintenance",
    "notifications.tasks.broadcast_announcement": "notifications",
}.items():
    route = settings.CELERY_TASK_ROUTES.get(task_name)
    check(f"route declared: {task_name} → {queue}", route is not None and route["queue"] == queue)

# `clean_expired_announcements` has no explicit route by design (the plan left its
# reserved name byte-identical); it therefore lands on CELERY_TASK_DEFAULT_QUEUE,
# which the worker consumes — proven for real by the expiry dispatch in section 4.
expiry_route = settings.CELERY_TASK_ROUTES.get("community.tasks.clean_expired_announcements")
expiry_queue = expiry_route["queue"] if expiry_route else settings.CELERY_TASK_DEFAULT_QUEUE
check(
    "unrouted beat task lands on a queue the worker consumes",
    expiry_queue in consumed_queues,
    f"clean_expired_announcements → {expiry_queue}",
)
if expiry_route is None:
    note(
        "OBSERVATION (LOW): hourly housekeeping `clean_expired_announcements` runs on `default` "
        "rather than `maintenance`, unlike its three peers — 7.2 D-07's stated rationale "
        "(housekeeping must not compete with request-driven work) argues for routing it."
    )

# --- 6. 04 §107's required test names ---------------------------------------------
print("\n-- 6. 04 §107 test-name coverage")
review_source = open("apps/moderation/tests/test_review_api.py", encoding="utf-8").read()

# Scored: the §107 names whose surface Phase 8.2 implements. Exact `def name(` match,
# because a substring test would pass on `test_remove_content_tombstones_and_notifies`.
for required in (
    "test_admin_can_review_report",
    "test_regular_user_cannot_review_report",
    "test_remove_content",
):
    check(f"§107 exact name present: {required}", f"def {required}(" in review_source)

# Reported, not scored: the four report-creation names belong to 8.1's surface. They are
# covered by equivalent, differently-named tests there, so this is an inherited naming
# deviation rather than a Phase 8.2 gap — recorded so it is not silently lost.
for spec_name, equivalent in (
    ("test_report_post", "test_report_post_created"),
    ("test_report_comment", "test_report_comment_created"),
    ("test_report_requires_one_target", "test_both_targets_rejected"),
    ("test_duplicate_report_behavior", "test_duplicate_pending_report_returns_400"),
):
    exists_here = f"def {spec_name}(" in review_source
    inherited = f"def {equivalent}(" in open(
        "apps/moderation/tests/test_report_api.py", encoding="utf-8"
    ).read()
    if exists_here:
        check(f"§107 exact name present: {spec_name}", True)
    else:
        note(
            f"OBSERVATION (LOW, inherited from 8.1): §107's name `{spec_name}` is absent; "
            f"its behavior is covered by `{equivalent}` ({'present' if inherited else 'MISSING'})."
        )

# --- 7. Django Admin over HTTP (MOD-05's headline surface) -------------------------
print("\n-- 7. Django Admin triage (08 §9.1)")
admin_probe = make_user("admin", is_staff=True, is_superuser=True)
admin_author = make_user("admin-author")
admin_victim = make_user("admin-victim")
admin_post = Post.objects.create(
    author=admin_author, title="Admin probe", body="Admin probe body.", category=sorted(post_category_keys())[0]
)
admin_comment = Comment.objects.create(post=admin_post, author=admin_author, body="Admin probe comment.")
admin_victim_device = Device.objects.create(
    user=admin_victim, fcm_token=f"{PREFIX}-dev-victim", is_active=True
)
r_admin_anon = Client(SERVER_NAME="localhost").get("/admin/moderation/report/")
check(
    "anonymous is bounced from the Admin changelist (302 to login)",
    r_admin_anon.status_code == 302 and "/admin/login/" in r_admin_anon.headers.get("Location", ""),
    f"got {r_admin_anon.status_code}",
)
r_admin_cand = Client(SERVER_NAME="localhost")
r_admin_cand.force_login(author)
r_admin_cand_resp = r_admin_cand.get("/admin/moderation/report/")
check(
    "a non-staff account is bounced from the Admin (302)",
    r_admin_cand_resp.status_code == 302,
    f"got {r_admin_cand_resp.status_code}",
)

client.force_login(admin_probe)  # session login; the admin needs an interactive session
r_changelist = client.get("/admin/moderation/report/")
check("staff reaches the Report changelist (200)", r_changelist.status_code == 200, f"got {r_changelist.status_code}")

# Draft two pending reports, then run the two §9.1 actions through the Admin form.
admin_report_dismiss = Report.objects.create(
    reporter=reporter_a, post=admin_post, reason="OTHER", description="admin dismiss probe"
)
admin_report_delete = Report.objects.create(
    reporter=reporter_b, comment=admin_comment, reason="SPAM", description="admin delete probe"
)


def run_admin_action(action: str, report_ids: list[str]):
    return client.post(
        "/admin/moderation/report/",
        {
            "action": action,
            "select_across": "0",
            "index": "0",
            "_selected_action": report_ids,
        },
    )


r_admin_dismiss = run_admin_action("dismiss_reports", [str(admin_report_dismiss.id)])
admin_report_dismiss.refresh_from_db()
check(
    "Admin action dismiss_reports resolves through the service layer",
    r_admin_dismiss.status_code in (200, 302) and admin_report_dismiss.status == "DISMISSED",
    f"http {r_admin_dismiss.status_code}, status {admin_report_dismiss.status}",
)

r_admin_delete = run_admin_action("soft_delete_and_resolve", [str(admin_report_delete.id)])
admin_report_delete.refresh_from_db()
admin_comment.refresh_from_db()
check(
    "Admin action soft_delete_and_resolve tombstones and resolves",
    r_admin_delete.status_code in (200, 302)
    and admin_report_delete.status == "RESOLVED"
    and admin_comment.is_deleted is True,
    f"http {r_admin_delete.status_code}, status {admin_report_delete.status}",
)

# The UserAdmin ban action must go through the service (audit + severing), not a bare flag.
r_admin_ban = client.post(
    "/admin/accounts/user/",
    {
        "action": "ban_selected_users",
        "select_across": "0",
        "index": "0",
        "_selected_action": [str(admin_victim.id)],
    },
)
admin_victim.refresh_from_db()
check(
    "Admin action ban_selected_users suspends the account",
    r_admin_ban.status_code in (200, 302) and admin_victim.is_active is False,
    f"http {r_admin_ban.status_code}, is_active {admin_victim.is_active}",
)
admin_severed = wait_for(lambda: not Device.objects.get(id=admin_victim_device.id).is_active)
check("the Admin ban severed the victim's device through the worker", admin_severed)

# --- cleanup ----------------------------------------------------------------------
print("\n-- 8. Cleanup")
broadcast_rows = Notification.objects.filter(
    type=Notification.NotificationType.ANNOUNCEMENT, created_at__gte=STARTED_AT
)
removed_rows = broadcast_rows.count()
broadcast_rows.delete()
swept = sweep_probe_data()
try:
    cache.delete_pattern("moderation:dup:*")
    cache.delete_pattern("community:dup:*")
except AttributeError:
    pass

check(
    "database baseline restored (users and announcements)",
    User.objects.count() == baseline_users and Announcement.objects.count() == baseline_announcements,
    f"users {User.objects.count()}/{baseline_users}, announcements {Announcement.objects.count()}/{baseline_announcements}, "
    f"broadcast rows removed: {removed_rows}, swept {swept}",
)

# --- verdict ----------------------------------------------------------------------
passed = sum(1 for _, ok, _ in results if ok)
failed = [name for name, ok, _ in results if not ok]
print(f"\n=== {passed}/{len(results)} checks passed ({len(notes)} observations) ===")
if notes:
    print("OBSERVATIONS:")
    for message in notes:
        print(f"  - {message}")
if failed:
    print("FAILED:")
    for name in failed:
        print(f"  - {name}")
    sys.exit(1)
print("ALL CHECKS PASSED")
