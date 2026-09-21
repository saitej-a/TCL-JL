"""Shared fixtures for the accounts auth suite."""

import pytest
from django.core import mail
from django.core.cache import cache as django_cache
from rest_framework.test import APIClient


@pytest.fixture
def api():
    """DRF test client (supports force_authenticate, unlike pytest-django's)."""
    return APIClient()


@pytest.fixture(autouse=True)
def deterministic_mail(settings):
    """Locmem backend + eager Celery regardless of which settings module the
    runner picked, so ``mail.outbox`` assertions hold in-process (a real broker
    would deliver to the worker container's console backend, not this process)."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    mail.outbox.clear()


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Isolate rate-limit buckets between tests (LocMemCache under test settings)."""
    django_cache.clear()
