"""App config for the timeline domain (T4.1)."""

from django.apps import AppConfig


class TimelineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.timeline"
    verbose_name = "Timeline"
