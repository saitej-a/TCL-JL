"""Tests for community cohort aggregations (Phase 7.1, ANAL-01, ANAL-02).

Phase 7.2 D-01 moved the `<5` floor from the slice total onto each result row, so
the aggregation tests below seed every bucket above the floor to keep asserting
*math*, and the floor behaviour itself is asserted separately (and in
`test_privacy_suppression.py`).
"""

from datetime import date

import pytest
from django.test import override_settings

from apps.analytics.services import (
    BASELINE_OFFER_LETTER,
    BASELINE_READINESS_SURVEY,
    DATA_SOURCE_LABEL,
    DISCLAIMER_TEXT,
    InvalidAnalyticsFilter,
    apply_row_floor,
    get_batch_breakdown,
    get_community_overview_stats,
    get_hiring_type_breakdown,
    get_region_breakdown,
    validate_filters,
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
    # 5 in batch 2024 (at the floor, since 7.2 D-01 floors each row)
    for _ in range(5):
        make_profile(
            batch="2024", current_status=CandidateProfile.Status.WAITING_FOR_JOINING_LETTER
        )
    # 7 in batch 2025
    for _ in range(7):
        make_profile(batch="2025", current_status=CandidateProfile.Status.JOINING_LETTER_RECEIVED)

    res = get_batch_breakdown()
    assert res["suppressed"] is False
    assert res["total_in_cohort"] == 12
    results = {row["batch"]: row for row in res["results"]}

    assert "2024" in results
    assert results["2024"]["candidate_count"] == 5
    assert results["2024"]["waiting_for_joining_letter"] == 5
    assert results["2024"]["joining_letter_reported"] == 0

    assert "2025" in results
    assert results["2025"]["candidate_count"] == 7
    assert results["2025"]["waiting_for_joining_letter"] == 0
    assert results["2025"]["joining_letter_reported"] == 7


def test_hiring_type_breakdown_aggregation(make_profile):
    for _ in range(6):
        make_profile(hiring_type=CandidateProfile.HiringType.DIGITAL)
    for _ in range(5):
        make_profile(hiring_type=CandidateProfile.HiringType.PRIME)

    res = get_hiring_type_breakdown()
    assert res["suppressed"] is False
    assert res["total_in_cohort"] == 11
    stream_map = {row["hiring_type"]: row["candidate_count"] for row in res["results"]}
    assert stream_map[CandidateProfile.HiringType.DIGITAL] == 6
    assert stream_map[CandidateProfile.HiringType.PRIME] == 5


def test_region_breakdown_aggregation(make_profile):
    for _ in range(5):
        make_profile(region="Karnataka")
    for _ in range(6):
        make_profile(region="Telangana")

    res = get_region_breakdown()
    assert res["suppressed"] is False
    assert res["total_in_cohort"] == 11
    reg_map = {row["region"]: row["candidate_count"] for row in res["results"]}
    assert reg_map["Karnataka"] == 5
    assert reg_map["Telangana"] == 6


def test_row_floor_drops_only_the_small_bucket(make_profile):
    """7.2 D-01: a below-floor bucket vanishes while larger siblings are served.

    This is the exact vector 4.2's residual-risk note named: before 7.2, a slice of
    9 could emit a batch row reporting 3 candidates.
    """
    for _ in range(6):
        make_profile(batch="2025")
    for _ in range(3):
        make_profile(batch="2024")

    res = get_batch_breakdown()
    assert res["suppressed"] is False
    assert res["total_in_cohort"] == 9

    batches = [row["batch"] for row in res["results"]]
    assert batches == ["2025"]
    # The small row is gone entirely: not zeroed, not labeled, not counted.
    assert all(row["candidate_count"] >= 5 for row in res["results"])
    assert "2024" not in batches


def test_row_floor_suppresses_when_no_bucket_survives(make_profile):
    """7.2 D-02: slice above the floor, every bucket below it -> 04 §53 payload."""
    for _ in range(4):
        make_profile(region="Karnataka")
    for _ in range(4):
        make_profile(region="Telangana")

    res = get_region_breakdown()
    assert res["suppressed"] is True
    assert res["message"] == ("Not enough community data to display this breakdown.")
    assert "results" not in res
    assert "total_in_cohort" not in res


def test_apply_row_floor_helper():
    """The floor is inclusive at the threshold and drops everything below it."""
    rows = [
        {"candidate_count": 2},
        {"candidate_count": 4},
        {"candidate_count": 5},
        {"candidate_count": 9},
    ]
    assert apply_row_floor(rows) == [{"candidate_count": 5}, {"candidate_count": 9}]
    assert apply_row_floor([{"candidate_count": 1}]) is None
    assert apply_row_floor([]) is None


@override_settings(ANALYTICS_MIN_COHORT_SIZE=3)
def test_row_floor_follows_the_same_setting(make_profile):
    """7.2 D-03: one setting governs the slice floor and the row floor."""
    for _ in range(5):
        make_profile(batch="2025")
    for _ in range(3):
        make_profile(batch="2024")

    res = get_batch_breakdown()
    assert res["suppressed"] is False
    assert {row["batch"] for row in res["results"]} == {"2024", "2025"}


def test_generated_at_is_present_on_success_and_absent_when_suppressed(make_profile):
    """7.2 D-06: compute-time stamp on data payloads; 04 §53's shape stays four-key."""
    for _ in range(6):
        make_profile(batch="2025")

    res = get_community_overview_stats()
    assert res["generated_at"].endswith("Z")

    # Drop below the floor -> the suppressed payload keeps exactly four keys.
    CandidateProfile.objects.all().delete()
    for _ in range(2):
        make_profile()

    suppressed = get_community_overview_stats()
    assert suppressed["suppressed"] is True
    assert set(suppressed) == {"data_source", "disclaimer", "suppressed", "message"}


def test_overview_publishes_both_wait_time_baselines(make_profile, make_timeline_event):
    """7.2 D-13/D-14: both intervals ride the overview payload, each disclosed.

    Note the samples are **not** the same candidates: the five survey-only profiles
    have no offer or interview baseline anywhere in D1's chain, so they cannot enter
    the offer metric. That asymmetry is exactly why both metrics are published with
    their own sample size and source counts (D-16) rather than merged into one
    average that would look equally well-evidenced.
    """
    for i in range(6):
        profile = make_profile(batch="2025")
        make_timeline_event(profile, "OFFER_LETTER", date(2025, 1, 1))
        make_timeline_event(profile, "JOINING_LETTER", date(2025, 3, 1 + i))
    for i in range(5):
        profile = make_profile(batch="2025")
        make_timeline_event(profile, "READINESS_SURVEY", date(2025, 2, 1))
        make_timeline_event(profile, "JOINING_LETTER", date(2025, 3, 10 + i))

    res = get_community_overview_stats()
    wait_times = res["wait_times"]

    offer_metric = wait_times["offer_to_joining_letter"]
    assert offer_metric["suppressed"] is False
    assert offer_metric["baseline"] == BASELINE_OFFER_LETTER
    assert offer_metric["sample_size"] == 6
    assert offer_metric["baseline_source_counts"]["OFFER_LETTER_EVENT"] == 6
    assert sum(offer_metric["baseline_source_counts"].values()) == 6

    survey_metric = wait_times["survey_to_joining_letter"]
    assert survey_metric["suppressed"] is False
    assert survey_metric["baseline"] == BASELINE_READINESS_SURVEY
    assert survey_metric["sample_size"] == 5
    assert survey_metric["baseline_source_counts"]["READINESS_SURVEY_EVENT"] == 5

    # The two intervals are materially different numbers, which is the whole
    # point of publishing them separately rather than redefining either one.
    assert survey_metric["average_days"] < offer_metric["average_days"]


def test_validate_filters_accepts_and_normalizes_known_values():
    assert validate_filters(hiring_type="digital", batch="2025", region="  Goa  ") == {
        "hiring_type": "DIGITAL",
        "batch": "2025",
        "region": "goa",
    }
    assert validate_filters() == {}


def test_validate_filters_rejects_unknown_values():
    """7.2 D-12: unknown values are refused, never silently widened."""
    with pytest.raises(InvalidAnalyticsFilter) as excinfo:
        validate_filters(hiring_type="SENIOR")
    assert excinfo.value.param == "hiring_type"
    assert "DIGITAL" in excinfo.value.allowed

    with pytest.raises(InvalidAnalyticsFilter) as excinfo:
        validate_filters(batch="2019")
    assert excinfo.value.param == "batch"

    with pytest.raises(InvalidAnalyticsFilter) as excinfo:
        validate_filters(region="<script>alert(1)</script>")
    assert excinfo.value.param == "region"

    with pytest.raises(InvalidAnalyticsFilter):
        validate_filters(region="x" * 101)
