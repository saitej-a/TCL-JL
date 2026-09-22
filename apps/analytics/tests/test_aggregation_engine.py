"""Tests for community cohort aggregations (Phase 7.1, ANAL-01, ANAL-02)."""

import pytest

from apps.analytics.services import (
    DATA_SOURCE_LABEL,
    DISCLAIMER_TEXT,
    get_batch_breakdown,
    get_community_overview_stats,
    get_hiring_type_breakdown,
    get_region_breakdown,
)
from apps.candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db


def test_overview_stats_calculation(make_profile):
    # 3 registered (waiting)
    for _ in range(3):
        make_profile(current_status=CandidateProfile.Status.REGISTERED)
    # 2 waiting for JL (waiting)
    for _ in range(2):
        make_profile(current_status=CandidateProfile.Status.WAITING_FOR_JOINING_LETTER)
    # 1 joining letter received (JL reported)
    make_profile(current_status=CandidateProfile.Status.JOINING_LETTER_RECEIVED)
    # 1 joined (joined reported and JL reported)
    make_profile(current_status=CandidateProfile.Status.JOINED)

    # Total = 7 (>= 5 threshold)
    res = get_community_overview_stats()
    assert res["suppressed"] is False
    assert res["data_source"] == DATA_SOURCE_LABEL
    assert res["disclaimer"] == DISCLAIMER_TEXT
    assert res["total_candidates"] == 7
    assert res["waiting_for_joining_letter"] == 5  # 3 REGISTERED + 2 WAITING_FOR_JOINING_LETTER
    assert res["joining_letters_reported"] == 2  # 1 JOINING_LETTER_RECEIVED + 1 JOINED
    assert res["joined_reported"] == 1  # 1 JOINED


def test_batch_breakdown_aggregation(make_profile):
    # 3 in batch 2024
    for _ in range(3):
        make_profile(
            batch="2024", current_status=CandidateProfile.Status.WAITING_FOR_JOINING_LETTER
        )
    # 4 in batch 2025
    for _ in range(4):
        make_profile(batch="2025", current_status=CandidateProfile.Status.JOINING_LETTER_RECEIVED)

    res = get_batch_breakdown()
    assert res["suppressed"] is False
    assert res["total_in_cohort"] == 7
    results = {row["batch"]: row for row in res["results"]}

    assert "2024" in results
    assert results["2024"]["candidate_count"] == 3
    assert results["2024"]["waiting_for_joining_letter"] == 3
    assert results["2024"]["joining_letter_reported"] == 0

    assert "2025" in results
    assert results["2025"]["candidate_count"] == 4
    assert results["2025"]["waiting_for_joining_letter"] == 0
    assert results["2025"]["joining_letter_reported"] == 4


def test_hiring_type_breakdown_aggregation(make_profile):
    for _ in range(4):
        make_profile(hiring_type=CandidateProfile.HiringType.DIGITAL)
    for _ in range(2):
        make_profile(hiring_type=CandidateProfile.HiringType.PRIME)

    res = get_hiring_type_breakdown()
    assert res["suppressed"] is False
    assert res["total_in_cohort"] == 6
    stream_map = {row["hiring_type"]: row["candidate_count"] for row in res["results"]}
    assert stream_map[CandidateProfile.HiringType.DIGITAL] == 4
    assert stream_map[CandidateProfile.HiringType.PRIME] == 2


def test_region_breakdown_aggregation(make_profile):
    for _ in range(3):
        make_profile(region="Karnataka")
    for _ in range(3):
        make_profile(region="Telangana")

    res = get_region_breakdown()
    assert res["suppressed"] is False
    assert res["total_in_cohort"] == 6
    reg_map = {row["region"]: row["candidate_count"] for row in res["results"]}
    assert reg_map["Karnataka"] == 3
    assert reg_map["Telangana"] == 3
