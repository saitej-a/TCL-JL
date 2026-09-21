"""Celery application instance (T1.6) — broker db=1, results db=2 (D-05).

Queues: default | notifications | maintenance (09 §7.1). Beat schedule entries
reference task names that arrive with their apps in later phases; unknown-name
entries are inert until the tasks are registered.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("tcs_joining_tracker")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "prune-inactive-devices-daily": {
        "task": "notifications.tasks.prune_stale_devices",
        "schedule": crontab(hour=3, minute=0),  # daily 03:00 UTC (T6.11)
    },
    "clean-expired-announcements-hourly": {
        "task": "community.tasks.clean_expired_announcements",
        "schedule": crontab(minute=15),  # hourly :15 (T8.6)
    },
    "warm-analytics-cache-hourly": {
        "task": "analytics.tasks.warm_analytics_cache",
        "schedule": crontab(minute=45),  # hourly :45 (T7.8)
    },
}
