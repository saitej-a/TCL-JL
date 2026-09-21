"""Shared fixtures for the candidates API test suite."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile

VALID_PASSWORD = "Correct Horse Battery 9!"


@pytest.fixture
def api():
    """DRF test client (supports force_authenticate, unlike pytest-django's)."""
    return APIClient()


@pytest.fixture
def verified_user(db):
    return User.objects.create_user("profiled@example.com", VALID_PASSWORD, is_verified=True)


@pytest.fixture
def unverified_user(db):
    return User.objects.create_user("pending@example.com", VALID_PASSWORD, is_verified=False)


@pytest.fixture
def inactive_user(db):
    return User.objects.create_user(
        "suspended@example.com", VALID_PASSWORD, is_verified=True, is_active=False
    )


@pytest.fixture
def make_profile(db):
    def _make(user=None, **overrides) -> CandidateProfile:
        if user is None:
            user = User.objects.create_user(
                f"prof-{User.objects.count()}@example.com", VALID_PASSWORD, is_verified=True
            )
        defaults = dict(user=user, batch="2025", hiring_type="DIGITAL", region="Telangana")
        defaults.update(overrides)
        return CandidateProfile.objects.create(**defaults)

    return _make
