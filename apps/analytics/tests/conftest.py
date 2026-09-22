"""Shared pytest fixtures for apps/analytics tests (Phase 7.1; 7.2 adds HTTP)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.timeline.models import TimelineEvent


@pytest.fixture(autouse=True)
def clear_analytics_cache():
    """Keep the payload cache and throttle buckets out of each other's tests.

    `LocMemCache` lives for the whole pytest process (7.2 caches payloads), so
    without this a cached payload or a spent throttle bucket would leak from one
    test into the next.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Anonymous DRF client — every analytics endpoint is public (04 §6)."""
    return APIClient()


@pytest.fixture
def make_user():
    def _make(email: str | None = None, is_verified: bool = True) -> User:
        unique_email = email or f"candidate-{uuid.uuid4().hex[:8]}@example.com"
        return User.objects.create_user(
            email=unique_email,
            password="StrongPassword123!",
            is_verified=is_verified,
        )

    return _make


@pytest.fixture
def make_profile(make_user):
    def _make(
        user: User | None = None,
        batch: str = "2025",
        hiring_type: str = CandidateProfile.HiringType.DIGITAL,
        region: str = "Maharashtra",
        current_status: str = CandidateProfile.Status.REGISTERED,
        **extra: Any,
    ) -> CandidateProfile:
        u = user or make_user()
        return CandidateProfile.objects.create(
            user=u,
            batch=batch,
            hiring_type=hiring_type,
            region=region,
            current_status=current_status,
            **extra,
        )

    return _make


@pytest.fixture
def make_timeline_event():
    def _make(
        candidate: CandidateProfile,
        event_type: str,
        event_date: date,
        description: str = "",
    ) -> TimelineEvent:
        return TimelineEvent.objects.create(
            candidate=candidate,
            event_type=event_type,
            event_date=event_date,
            description=description,
        )

    return _make
