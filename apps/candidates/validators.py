"""Batch-year validation (3.1 D3): settings-driven cohort list (PROF-01)."""

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_batch_year(value: str) -> None:
    """Value must be a year offered in settings.BATCH_YEARS (string compare).

    Reads settings at call time so runtime changes (override_settings in
    tests, or adding 2027 in production) re-validate without a migration.
    """
    offered = [str(year) for year in getattr(settings, "BATCH_YEARS", [])]
    if str(value) not in offered:
        raise ValidationError(
            f"Batch '{value}' is not offered. Choose from: {', '.join(offered)}.",
            code="batch_not_offered",
        )
