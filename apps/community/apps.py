"""App config for the community domain (T5.1)."""

from django.apps import AppConfig


class CommunityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.community"
    verbose_name = "Community"
