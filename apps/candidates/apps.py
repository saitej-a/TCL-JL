"""App config for the candidates domain (T3.1)."""

from django.apps import AppConfig


class CandidatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.candidates"
    verbose_name = "Candidates"
