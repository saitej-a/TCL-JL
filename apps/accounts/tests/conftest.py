"""Shared fixtures for the accounts auth suite."""

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.fixture
def api():
    """DRF test client (supports force_authenticate, unlike pytest-django's)."""
    return APIClient()


@pytest.fixture(autouse=True)
def deterministic_mail(settings):
    """Locmem backend regardless of which settings module the runner picked,
    so ``mail.outbox`` assertions hold under local AND test settings."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()


@pytest.fixture(autouse=True)
def clear_throttle_cache(cache):
    """Isolate rate-limit buckets between tests (LocMemCache under test settings)."""
    cache.clear()
