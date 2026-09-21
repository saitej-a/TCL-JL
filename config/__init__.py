"""Global project configuration package.

DJANGO_SETTINGS_MODULE selects config.settings.local / config.settings.production.
The __init__ imports the Celery app (T1.6) so `celery -A config` and Django both
share one app instance.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
