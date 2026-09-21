"""Shared fixtures for the timeline service test suite."""

import pytest

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile

VALID_PASSWORD = "Correct Horse Battery 9!"


@pytest.fixture
def make_user(db):
    def _make(email: str | None = None) -> User:
        if email is None:
            email = f"tl-{User.objects.count()}@example.com"
        return User.objects.create_user(email, VALID_PASSWORD, is_verified=True)

    return _make


@pytest.fixture
def make_profile(db):
    def _make(user: User | None = None, **overrides) -> CandidateProfile:
        if user is None:
            user = User.objects.create_user(
                f"tl-prof-{User.objects.count()}@example.com", VALID_PASSWORD, is_verified=True
            )
        defaults = dict(user=user, batch="2025", hiring_type="DIGITAL", region="Telangana")
        defaults.update(overrides)
        return CandidateProfile.objects.create(**defaults)

    return _make
