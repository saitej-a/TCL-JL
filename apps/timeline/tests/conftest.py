"""Shared fixtures for the timeline test suite (4.1 services + 4.2 API)."""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.timeline.models import TimelineEvent

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


@pytest.fixture
def make_unverified_user(db):
    return User.objects.create_user("tl-unverified@example.com", VALID_PASSWORD, is_verified=False)


@pytest.fixture
def make_inactive_user(db):
    return User.objects.create_user("tl-inactive@example.com", VALID_PASSWORD, is_active=False)


def make_profile_for(user: User, **overrides) -> CandidateProfile:
    """Module-level helper for 4.2 tests that build several candidates."""
    defaults = dict(user=user, batch="2025", hiring_type="DIGITAL", region="Telangana")
    defaults.update(overrides)
    return CandidateProfile.objects.create(**defaults)


@pytest.fixture
def api(db):
    """Unauthenticated DRF client."""
    return APIClient()


@pytest.fixture
def auth_api(db):
    """Factory: `auth_api(user)` -> a client authenticated as that user.

    `force_authenticate` bypasses the JWT layer but still exercises the
    permission classes (IsAuthenticated/IsActive/IsVerified), which is where the
    4.2 gating actually lives.
    """

    def _make(user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _make


@pytest.fixture
def make_event(db):
    """Create a TimelineEvent directly — bypasses the status-sync service so
    4.2 tests can isolate API behaviour from 4.1's walk."""

    def _make(
        profile: CandidateProfile,
        *,
        event_type: str = "INTERVIEW",
        event_date: date = date(2026, 9, 18),
        description: str = "",
        is_verified: bool = False,
    ) -> TimelineEvent:
        return TimelineEvent.objects.create(
            candidate=profile,
            event_type=event_type,
            event_date=event_date,
            description=description,
            is_verified=is_verified,
        )

    return _make
