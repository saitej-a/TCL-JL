"""Stage 2 live drill for PLAN 06.1-01 (run inside the web container:
python manage.py shell < drill_06_01.py).

6.1 is model-only, so unlike 5.2's HTTP drill this one is ORM against the real
dev database: it proves the check constraint, the token uniqueness, the unread
count, and the lazy preferences at the layer that holds them, then cleans up
after itself. Every check prints PASS/FAIL and the script exits non-zero on any
failure.
"""

import uuid as uuidlib

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.notifications.models import Device, Notification, NotificationPreference

User = get_user_model()
PASSWORD = "Correct Horse Battery 9!"
STAMP = uuidlib.uuid4().hex[:8]

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))


def make_user(tag):
    return User.objects.create_user(
        f"drill-06.1-{tag}-{STAMP}@example.com", PASSWORD, is_verified=True
    )


def attempt(fn):
    """Run a write that must be refused, return the exception class name."""
    try:
        with transaction.atomic():
            fn()
    except Exception as exc:  # noqa: BLE001 - the drill reports whatever the DB raises
        return type(exc).__name__
    return "NO EXCEPTION"


user_a, user_b = make_user("a"), make_user("b")

try:
    # --- laziness: no preference row exists for a fresh user (R6) --------------
    check(
        "1. fresh user has no preference row",
        NotificationPreference.objects.filter(user=user_a).count() == 0,
        f"count={NotificationPreference.objects.filter(user=user_a).count()}",
    )

    # --- the unread-count seam (D6) -------------------------------------------
    for index in range(3):
        Notification.objects.create(
            recipient=user_a,
            title=f"Drill notification {index}",
            message="Live drill row.",
        )
    check(
        "2. unread_count_for(A) == 3",
        Notification.objects.unread_count_for(user_a) == 3,
        str(Notification.objects.unread_count_for(user_a)),
    )
    check(
        "3. unread_count_for(B) == 0 (recipient-scoped)",
        Notification.objects.unread_count_for(user_b) == 0,
        str(Notification.objects.unread_count_for(user_b)),
    )

    # --- index shape: the count must not sort (R-5) ---------------------------
    with connection.cursor() as cursor:
        cursor.execute(
            "EXPLAIN SELECT COUNT(*) FROM notifications_notification "
            "WHERE recipient_id = %s AND is_read = false",
            [str(user_a.pk)],
        )
        plan = "\n".join(row[0] for row in cursor.fetchall())
    print(f"     count plan: {plan}")
    check("4. count plan contains no Sort", "Sort" not in plan)
    # The planner picks between the two compound indexes by cost: on a handful of
    # rows it prefers the narrower (recipient, created_at) index and filters
    # is_read, on a large unread-heavy mailbox the (recipient, is_read, created_at)
    # index becomes the cheaper one. What 6.1 guarantees is the index *shape* (the
    # psql \d proof) and the absence of a sort — not a specific runtime choice.
    chosen = [name for name in ("idx_notif_recip_read_created", "idx_notif_recipient_created") if name in plan]
    check(
        "5. count plan uses a notification index (planner picks by cost)",
        bool(chosen) and "Seq Scan" not in plan,
        ",".join(chosen) or plan,
    )

    # --- the sanctioned pair writer (R4) --------------------------------------
    first = Notification.objects.filter(recipient=user_a).order_by("created_at").first()
    flipped = first.mark_as_read()
    first.refresh_from_db()
    check(
        "6. mark_as_read flips both fields and returns True",
        flipped is True and first.is_read is True and first.read_at is not None,
        f"is_read={first.is_read} read_at={first.read_at}",
    )
    read_at_after_first = first.read_at
    check("7. second mark_as_read returns False", first.mark_as_read() is False)
    first.refresh_from_db()
    check(
        "8. read_at unmoved on the idempotent call",
        first.read_at == read_at_after_first,
        f"{first.read_at} vs {read_at_after_first}",
    )
    check(
        "9. unread_count_for(A) == 2 after one mark-read",
        Notification.objects.unread_count_for(user_a) == 2,
        str(Notification.objects.unread_count_for(user_a)),
    )

    # --- the constraint, live --------------------------------------------------
    observer = Notification.objects.filter(recipient=user_a, is_read=False).first()
    error = attempt(
        lambda: Notification.objects.filter(pk=observer.pk).update(is_read=True, read_at=None)
    )
    check("10. raw update to read-without-timestamp refused", error == "IntegrityError", error)
    observer.refresh_from_db()
    check(
        "11. refused row unchanged (rollback)",
        observer.is_read is False and observer.read_at is None,
        f"is_read={observer.is_read} read_at={observer.read_at}",
    )
    error = attempt(
        lambda: Notification.objects.create(
            recipient=user_a, is_read=True, read_at=None, title="illegal", message="illegal"
        )
    )
    check("12. create with the illegal pair refused", error == "IntegrityError", error)

    # --- bulk mark-all-read: 6.2's obligation, both columns in one UPDATE ------
    updated = Notification.objects.filter(recipient=user_a, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    check(
        "13. bulk mark-all-read (both columns) accepted, count now 0",
        updated == 2 and Notification.objects.unread_count_for(user_a) == 0,
        f"updated={updated} count={Notification.objects.unread_count_for(user_a)}",
    )

    # --- the application mirror ------------------------------------------------
    mirror = Notification(recipient=user_b, is_read=True, read_at=None, title="x", message="y")
    try:
        mirror.clean()
    except ValidationError as exc:
        code = exc.error_dict["read_at"][0].code
        check("14. clean() raises read_state_inconsistent", code == "read_state_inconsistent", code)
    else:
        check("14. clean() raises read_state_inconsistent", False, "no ValidationError")

    # --- devices --------------------------------------------------------------
    device = Device.objects.create(user=user_b, fcm_token=f"drill-token-{STAMP}", browser="Drill")
    check(
        "15. Device.__str__ hides token and email",
        "drill-token" not in str(device) and "@example.com" not in str(device),
        str(device),
    )
    error = attempt(
        lambda: Device.objects.create(user=user_b, fcm_token=f"drill-token-{STAMP}")
    )
    check("16. duplicate fcm_token refused by the unique column", error == "IntegrityError", error)
    Device.objects.create(user=user_b, fcm_token=f"drill-token-second-{STAMP}", browser="Drill")
    check(
        "17. two tokens for one user are both allowed (multi-device)",
        user_b.devices.count() == 2,
        str(user_b.devices.count()),
    )

    # --- lazy preferences (R6) -------------------------------------------------
    pref_one, created_one = NotificationPreference.get_or_create_for(user_b)
    pref_two, created_two = NotificationPreference.get_or_create_for(user_b)
    check(
        "18. get_or_create_for is idempotent",
        created_one is True and created_two is False and pref_one.pk == pref_two.pk,
        f"created={created_one},{created_two}",
    )
    check(
        "19. preferences reachable from the user",
        user_b.notification_preferences.pk == pref_one.pk,
    )
    check(
        "20. all six preference flags default True",
        all(
            getattr(pref_one, flag) is True
            for flag in (
                "notify_on_comment",
                "notify_on_reply",
                "notify_on_vote_milestone",
                "notify_on_announcements",
                "notify_timeline_reminders",
                "push_enabled",
            )
        ),
    )

    # --- cascade wiring, live (R8: dormant by design, still real) --------------
    user_b_pk = user_b.pk
    notification_ids = list(Notification.objects.filter(recipient=user_b).values_list("id", flat=True))
    user_b.delete()
    check(
        "21. user delete cascades notifications/devices/preferences",
        not Notification.objects.filter(id__in=notification_ids).exists()
        and not Device.objects.filter(user_id=user_b_pk).exists()
        and not NotificationPreference.objects.filter(user_id=user_b_pk).exists(),
        f"notifications={Notification.objects.filter(id__in=notification_ids).count()} "
        f"devices={Device.objects.filter(user_id=user_b_pk).count()} "
        f"prefs={NotificationPreference.objects.filter(user_id=user_b_pk).count()}",
    )
finally:
    drill_users = User.objects.filter(email__endswith=f"-{STAMP}@example.com")
    leftover = drill_users.count()
    drill_users.delete()
    print(f"\ncleanup: deleted {leftover} drill user(s) and their cascades")

failed = [name for name, ok, _detail in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} live ORM checks passed")
if failed:
    print("FAILURES:", failed)
    raise SystemExit(1)
