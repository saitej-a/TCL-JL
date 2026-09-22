"""Tests for wait-time calculation logic and fallback hierarchy (Phase 7.1, ANAL-03)."""

from datetime import date, timedelta

import pytest

from apps.analytics.services import (
    DATA_SOURCE_LABEL,
    DISCLAIMER_TEXT,
    SUPPRESSED_MESSAGE,
    calculate_wait_time_metrics,
)
from apps.timeline.models import TimelineEvent

pytestmark = pytest.mark.django_db


def test_wait_time_offer_to_jl_happy_path(make_profile, make_timeline_event):
    # 5 candidates with OFFER_LETTER -> JOINING_LETTER (wait times: 10, 20, 30, 40, 50 days)
    wait_days = [10, 20, 30, 40, 50]
    for days in wait_days:
        p = make_profile()
        offer_date = date(2026, 1, 1)
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.OFFER_LETTER,
            event_date=offer_date,
        )
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=offer_date + timedelta(days=days),
        )

    res = calculate_wait_time_metrics()
    assert res["suppressed"] is False
    assert res["data_source"] == DATA_SOURCE_LABEL
    assert res["disclaimer"] == DISCLAIMER_TEXT
    assert res["sample_size"] == 5
    assert res["average_days"] == 30.0
    assert res["median_days"] == 30.0
    assert res["min_days"] == 10
    assert res["max_days"] == 50


def test_wait_time_fallback_to_interview_event(make_profile, make_timeline_event):
    # 5 candidates with no OFFER_LETTER, but having INTERVIEW -> JOINING_LETTER
    for _ in range(5):
        p = make_profile()
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.INTERVIEW,
            event_date=date(2026, 1, 1),
        )
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=date(2026, 1, 21),  # 20 days
        )

    res = calculate_wait_time_metrics()
    assert res["suppressed"] is False
    assert res["sample_size"] == 5
    assert res["average_days"] == 20.0
    assert res["median_days"] == 20.0


def test_wait_time_fallback_to_profile_dates(make_profile, make_timeline_event):
    # 5 candidates without baseline TimelineEvents, but with offer_letter_date /
    # interview_date present on CandidateProfile
    # 3 candidates with profile offer_letter_date (15 days)
    for _ in range(3):
        p = make_profile(offer_letter_date=date(2026, 1, 1))
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=date(2026, 1, 16),
        )

    # 2 candidates with profile interview_date (25 days)
    for _ in range(2):
        p = make_profile(interview_date=date(2026, 1, 1))
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=date(2026, 1, 26),
        )

    res = calculate_wait_time_metrics()
    assert res["suppressed"] is False
    assert res["sample_size"] == 5
    # (15*3 + 25*2) / 5 = 95 / 5 = 19.0
    assert res["average_days"] == 19.0
    assert res["median_days"] == 15.0
    assert res["min_days"] == 15
    assert res["max_days"] == 25


def test_wait_time_prefers_offer_event_over_interview_event(make_profile, make_timeline_event):
    # Candidate with both INTERVIEW and OFFER_LETTER -> should pick OFFER_LETTER
    for _ in range(5):
        p = make_profile()
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.INTERVIEW,
            event_date=date(2026, 1, 1),
        )
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.OFFER_LETTER,
            event_date=date(2026, 1, 10),
        )
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=date(2026, 1, 20),  # 10 days from offer
        )

    res = calculate_wait_time_metrics()
    assert res["suppressed"] is False
    assert res["average_days"] == 10.0


def test_wait_time_suppressed_when_sample_size_below_threshold(make_profile, make_timeline_event):
    # Only 3 candidates with JL (< 5)
    for _ in range(3):
        p = make_profile()
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.OFFER_LETTER,
            event_date=date(2026, 1, 1),
        )
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=date(2026, 1, 15),
        )

    res = calculate_wait_time_metrics()
    assert res["suppressed"] is True
    assert res["message"] == SUPPRESSED_MESSAGE
    assert "average_days" not in res
    assert "sample_size" not in res


def test_wait_time_empty_population():
    res = calculate_wait_time_metrics()
    assert res["suppressed"] is True
    assert res["message"] == SUPPRESSED_MESSAGE


def test_wait_time_excludes_negative_intervals(make_profile, make_timeline_event):
    """Anomalous rows (JL dated before its baseline) never enter the sample."""
    # 5 valid candidates: exactly 30 days each.
    for _ in range(5):
        p = make_profile()
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.OFFER_LETTER,
            event_date=date(2026, 1, 1),
        )
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=date(2026, 1, 31),
        )

    # 2 anomalous candidates: JL recorded before the offer letter (negative interval).
    for _ in range(2):
        p = make_profile()
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.OFFER_LETTER,
            event_date=date(2026, 3, 1),
        )
        make_timeline_event(
            candidate=p,
            event_type=TimelineEvent.EventType.JOINING_LETTER,
            event_date=date(2026, 2, 1),
        )

    res = calculate_wait_time_metrics()
    assert res["suppressed"] is False
    # The 2 anomalies are excluded, so the sample stays at the 5 valid candidates.
    assert res["sample_size"] == 5
    assert res["average_days"] == 30.0
    assert res["median_days"] == 30.0
    assert res["min_days"] == 30
    assert res["max_days"] == 30
