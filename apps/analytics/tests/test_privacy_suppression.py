"""Tests for mandatory <5 candidate privacy suppression (Phase 7.1, ANAL-04)."""

import pytest
from django.test import override_settings

from apps.analytics.services import (
    DATA_SOURCE_LABEL,
    DISCLAIMER_TEXT,
    SUPPRESSED_MESSAGE,
    check_privacy_suppression,
    get_batch_breakdown,
    get_community_overview_stats,
    get_hiring_type_breakdown,
    get_region_breakdown,
)
from apps.candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db


def test_check_privacy_suppression_helper():
    # Below default threshold (5)
    for c in [0, 1, 2, 3, 4]:
        suppressed, payload = check_privacy_suppression(c)
        assert suppressed is True
        assert payload is not None
        assert payload["suppressed"] is True
        assert payload["data_source"] == DATA_SOURCE_LABEL
        assert payload["disclaimer"] == DISCLAIMER_TEXT
        assert payload["message"] == SUPPRESSED_MESSAGE

    # At or above threshold (5)
    for c in [5, 6, 100]:
        suppressed, payload = check_privacy_suppression(c)
        assert suppressed is False
        assert payload is None


def test_overview_suppression_when_below_threshold(make_profile):
    # Seed 3 candidates (< 5)
    for _ in range(3):
        make_profile()

    res = get_community_overview_stats()
    assert res["suppressed"] is True
    assert res["message"] == SUPPRESSED_MESSAGE
    assert "total_candidates" not in res
    assert "waiting_for_joining_letter" not in res


def test_batch_breakdown_suppression_when_filtered_cohort_below_threshold(make_profile):
    # Seed 6 candidates in batch 2025 (>= 5), but only 2 in Goa
    for _ in range(4):
        make_profile(batch="2025", region="Maharashtra")
    for _ in range(2):
        make_profile(batch="2025", region="Goa")

    # Overall batch query (6 candidates) -> not suppressed
    res_all = get_batch_breakdown()
    assert res_all["suppressed"] is False
    assert len(res_all["results"]) >= 1

    # Filtered by region=Goa (2 candidates) -> suppressed
    res_goa = get_batch_breakdown(region="Goa")
    assert res_goa["suppressed"] is True
    assert res_goa["message"] == SUPPRESSED_MESSAGE
    assert "results" not in res_goa


def test_hiring_type_breakdown_suppression_when_below_threshold(make_profile):
    # Seed 3 candidates with DIGITAL stream
    for _ in range(3):
        make_profile(hiring_type=CandidateProfile.HiringType.DIGITAL)

    res = get_hiring_type_breakdown(region="Delhi")
    assert res["suppressed"] is True
    assert res["message"] == SUPPRESSED_MESSAGE
    assert "results" not in res


def test_region_breakdown_suppression_when_below_threshold(make_profile):
    # 2 candidates in Kerala
    for _ in range(2):
        make_profile(region="Kerala")

    res = get_region_breakdown(batch="2025")
    assert res["suppressed"] is True
    assert res["message"] == SUPPRESSED_MESSAGE
    assert "results" not in res


def test_privacy_suppression_below_threshold(make_profile):
    """Threshold - 1 (4 candidates) suppresses every aggregation surface (ANAL-04).

    The boundary is exercised on all four helpers at once so a single helper
    leaking its breakdown below the floor cannot pass unnoticed.
    """
    for _ in range(4):
        make_profile(batch="2025", hiring_type=CandidateProfile.HiringType.PRIME)

    for payload in (
        get_community_overview_stats(),
        get_batch_breakdown(),
        get_hiring_type_breakdown(),
        get_region_breakdown(),
    ):
        assert payload["suppressed"] is True
        assert payload["message"] == SUPPRESSED_MESSAGE
        assert payload["data_source"] == DATA_SOURCE_LABEL
        assert payload["disclaimer"] == DISCLAIMER_TEXT
        assert "results" not in payload
        assert "total_candidates" not in payload
        assert "total_in_cohort" not in payload

    # 5 candidates (threshold) un-suppresses the same surface again.
    make_profile(batch="2025", hiring_type=CandidateProfile.HiringType.PRIME)
    assert get_community_overview_stats()["suppressed"] is False


@override_settings(ANALYTICS_MIN_COHORT_SIZE=3)
def test_suppression_threshold_dynamically_respects_settings(make_profile):
    # When threshold is tuned to 3, cohort of 3 is allowed
    for _ in range(3):
        make_profile()

    res = get_community_overview_stats()
    assert res["suppressed"] is False
    assert res["total_candidates"] == 3
