"""Moderation application configuration (Phase 8.1 — reports & heuristics)."""

from django.apps import AppConfig


class ModerationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.moderation"
    verbose_name = "Moderation"
