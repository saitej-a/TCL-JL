"""Celery wiring tests (Phase 8.2 — Task 6 step 3; the 6.2/7.2 name-mismatch lesson).

A Celery task name is a string, not an import path: `notifications.tasks.foo`
lives at `apps.notifications.tasks.foo`, and a beat/route entry naming a task
that was never implemented stays silently inert until it fires in production.
Phase 8.2's verification found exactly that class of defect (the reserved
announcement expiry entry pointed at a module that did not exist), so every
entry is resolved here against its real implementation.
"""

import importlib

import pytest
from django.conf import settings

from config.celery import app

# beat entry key -> (celery task name, python module, attribute)
EXPECTED_BEAT = {
    "prune-inactive-devices-daily": (
        "notifications.tasks.prune_stale_devices",
        "apps.notifications.tasks",
        "prune_stale_devices",
    ),
    "clean-expired-announcements-hourly": (
        "community.tasks.clean_expired_announcements",
        "apps.community.tasks",
        "clean_expired_announcements",
    ),
    "warm-analytics-cache-hourly": (
        "analytics.tasks.warm_analytics_cache",
        "apps.analytics.tasks",
        "warm_analytics_cache",
    ),
    "reinstate-suspended-users-hourly": (
        "moderation.tasks.auto_reinstate_users",
        "apps.moderation.tasks",
        "auto_reinstate_users",
    ),
}

# Task name -> the queue its route must declare.
EXPECTED_ROUTES = {
    "notifications.tasks.send_push_notification": "notifications",
    "notifications.tasks.broadcast_announcement": "notifications",
    "notifications.tasks.prune_stale_devices": "maintenance",
    "analytics.tasks.warm_analytics_cache": "maintenance",
    "moderation.tasks.sever_banned_user_sessions": "default",
    "moderation.tasks.auto_reinstate_users": "maintenance",
}


@pytest.mark.parametrize("entry", sorted(EXPECTED_BEAT))
def test_beat_entry_resolves_to_a_real_task(entry):
    """Every scheduled task actually exists, under the exact name it is scheduled by."""
    task_name, module_path, attribute = EXPECTED_BEAT[entry]
    assert entry in app.conf.beat_schedule, f"missing beat entry: {entry}"
    assert app.conf.beat_schedule[entry]["task"] == task_name

    module = importlib.import_module(module_path)  # ModuleNotFoundError = inert entry
    task = getattr(module, attribute)
    assert task.name == task_name, (
        f"decorator name {task.name!r} does not byte-match the beat entry {task_name!r}"
    )


@pytest.mark.parametrize("task_name", sorted(EXPECTED_ROUTES))
def test_task_routes_point_at_real_tasks(task_name):
    """Every routed task exists, and its route declares the expected queue."""
    route = settings.CELERY_TASK_ROUTES.get(task_name)
    assert route is not None, f"unrouted task: {task_name}"
    assert route["queue"] == EXPECTED_ROUTES[task_name]


def test_announcement_broadcast_task_exists_with_reserved_name():
    """The route reserved in 6.2 now has an implementation (8.2 T8.10)."""
    from apps.notifications.tasks import broadcast_announcement

    assert broadcast_announcement.name == "notifications.tasks.broadcast_announcement"


def test_reinstate_task_is_scheduled_hourly():
    """D3's must-have: a temporary ban must actually lapse back (F1 from verification)."""
    schedule = app.conf.beat_schedule["reinstate-suspended-users-hourly"]["schedule"]
    assert schedule.minute == {25}
