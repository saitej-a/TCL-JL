"""§7.9 status-distribution endpoint tests (Phase 9.4, D1).

The one backend surface 9.4 adds. Covered here: the row map's completeness against
the model, the three-filter intersection, 7.2's suppression rules at slice and row
level over HTTP, the error envelope for a bad filter, the anonymous/read-only
posture, attribution, and the privacy guarantee that no candidate identifier can
reach this payload.

Deliberately not a re-test of `apply_row_floor` or `validate_filters` themselves —
7.1/7.2 own those; this module asserts the new wiring that uses them.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.analytics.services import (
    DATA_SOURCE_LABEL,
    DISCLAIMER_TEXT,
    STATUS_DISTRIBUTION_GROUPS,
    apply_row_floor,
)
from apps.analytics.throttles import AnalyticsReadRateThrottle
from apps.analytics.views import StatusDistributionView
from apps.candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db

URL_NAME = "analytics-status-distribution"


def _seed(make_profile, count: int, **kwargs):
    """Seed `count` candidates with identical profile attributes.

    Every caller keeps each slice/row at or above the `<5` floor unless it is
    deliberately testing a below-floor branch, so a passing test never depends on
    suppression accidentally.
    """
    return [make_profile(**kwargs) for _ in range(count)]


def test_every_status_choice_belongs_to_exactly_one_row():
    """The row map is total and disjoint over the model's vocabulary.

    A status the map forgot would vanish from a public distribution without any
    error, so completeness is pinned against `CandidateProfile.Status.values` —
    adding a status to the model fails this test until the map learns about it.
    """
    covered: list[str] = []
    for _, _, statuses in STATUS_DISTRIBUTION_GROUPS:
        covered.extend(statuses)

    assert len(covered) == len(set(covered)), "a status appears in two rows"
    assert set(covered) == set(CandidateProfile.Status.values)


def test_rows_map_each_status_into_its_spec_label(api_client, make_profile):
    """§7.9's five display rows, plus our Withdrawn/Other row, get the right counts."""
    per_status = [
        (CandidateProfile.Status.WAITING_FOR_JOINING_LETTER, "WAITING_FOR_JL", "Waiting for JL"),
        (CandidateProfile.Status.JOINING_LETTER_RECEIVED, "JL_RECEIVED", "JL Received"),
        (
            CandidateProfile.Status.JOINING_DATE_RECEIVED,
            "JOINING_DATE_RECEIVED",
            "Joining Date Received",
        ),
        (CandidateProfile.Status.JOINED, "JOINED", "Joined TCS"),
        (CandidateProfile.Status.REGISTERED, "SURVEY_OFFER_STAGE", "Survey / Offer stage"),
        (CandidateProfile.Status.INTERVIEWED, "SURVEY_OFFER_STAGE", "Survey / Offer stage"),
        (CandidateProfile.Status.SELECTED, "SURVEY_OFFER_STAGE", "Survey / Offer stage"),
        (CandidateProfile.Status.OFFER_RECEIVED, "SURVEY_OFFER_STAGE", "Survey / Offer stage"),
        (CandidateProfile.Status.READINESS_SURVEY, "SURVEY_OFFER_STAGE", "Survey / Offer stage"),
        (CandidateProfile.Status.WITHDRAWN, "WITHDRAWN_OTHER", "Withdrawn / Other"),
        (CandidateProfile.Status.OTHER, "WITHDRAWN_OTHER", "Withdrawn / Other"),
    ]
    for status, _, _ in per_status:
        _seed(make_profile, count=5, current_status=status)

    body = api_client.get(reverse(URL_NAME)).json()

    assert body["suppressed"] is False
    assert body["total_in_cohort"] == 55
    counts = {row["status_group"]: row["candidate_count"] for row in body["results"]}
    assert counts == {
        "WAITING_FOR_JL": 5,
        "JL_RECEIVED": 5,
        "JOINING_DATE_RECEIVED": 5,
        "JOINED": 5,
        "SURVEY_OFFER_STAGE": 25,
        "WITHDRAWN_OTHER": 10,
    }
    labels = [row["label"] for row in body["results"]]
    assert labels == [label for _, label, _ in STATUS_DISTRIBUTION_GROUPS]
    # §7.9's *Withdrawn / Other* row is the recorded divergence from the mockup's
    # five-row legend (the model has statuses the screen does not draw).
    assert labels[-1] == "Withdrawn / Other"
    assert [row["status_group"] for row in body["results"]][:4] == [
        "WAITING_FOR_JL",
        "JL_RECEIVED",
        "JOINING_DATE_RECEIVED",
        "JOINED",
    ]


def test_counts_sum_to_the_cohort_and_shares_sum_to_one_hundred(api_client, make_profile):
    """Every counted candidate lands in exactly one row, so nothing is lost."""
    _seed(make_profile, count=5, current_status=CandidateProfile.Status.REGISTERED)
    _seed(make_profile, count=5, current_status=CandidateProfile.Status.SELECTED)
    _seed(make_profile, count=5, current_status=CandidateProfile.Status.JOINED)

    body = api_client.get(reverse(URL_NAME)).json()

    assert body["total_in_cohort"] == 15
    assert sum(row["candidate_count"] for row in body["results"]) == 15
    assert sum(row["share"] for row in body["results"]) == pytest.approx(100.0, abs=0.2)
    assert {row["status_group"]: row["share"] for row in body["results"]} == {
        "SURVEY_OFFER_STAGE": pytest.approx(66.7, abs=0.1),
        "JOINED": pytest.approx(33.3, abs=0.1),
    }


def test_the_three_filters_intersect_rather_than_union(api_client, make_profile):
    """`?batch=&hiring_type=&region=` must narrow by all three, not any of them."""
    digital = CandidateProfile.HiringType.DIGITAL
    ninja = CandidateProfile.HiringType.NINJA
    # In the slice: 2025 + DIGITAL + Maharashtra.
    _seed(make_profile, count=6, batch="2025", hiring_type=digital, region="Maharashtra")
    # Each of the other three matches exactly two of the three filter values.
    _seed(make_profile, count=6, batch="2025", hiring_type=digital, region="Goa")
    _seed(make_profile, count=6, batch="2025", hiring_type=ninja, region="Maharashtra")
    _seed(make_profile, count=6, batch="2024", hiring_type=digital, region="Maharashtra")

    body = api_client.get(
        reverse(URL_NAME),
        {"batch": "2025", "hiring_type": "DIGITAL", "region": "Maharashtra"},
    ).json()

    assert body["total_in_cohort"] == 6
    assert sum(row["candidate_count"] for row in body["results"]) == 6

    # Each filter on its own matches three of the four cohorts (18) — so a single
    # 18 would not prove anything; only the intersection's 6 does.
    alone = {
        name: api_client.get(reverse(URL_NAME), {name: value}).json()["total_in_cohort"]
        for name, value in (
            ("batch", "2025"),
            ("hiring_type", "DIGITAL"),
            ("region", "Maharashtra"),
        )
    }
    assert alone == {"batch": 18, "hiring_type": 18, "region": 18}


@pytest.mark.parametrize(
    "filters",
    (
        {"batch": "2026"},
        {"hiring_type": "DIGITAL"},
        {"region": "Goa"},
        {"batch": "2026", "hiring_type": "DIGITAL", "region": "Goa"},
    ),
)
def test_a_slice_below_the_floor_returns_the_suppression_payload(api_client, make_profile, filters):
    """7.2 D-02 unchanged: four candidates disclose nothing, not four counts.

    The four-candidate cohort differs from the six-candidate one in all three filter
    dimensions, so each filter — alone or combined — selects exactly four.
    """
    _seed(
        make_profile,
        count=4,
        batch="2026",
        hiring_type=CandidateProfile.HiringType.DIGITAL,
        region="Goa",
    )
    _seed(
        make_profile,
        count=6,
        batch="2025",
        hiring_type=CandidateProfile.HiringType.NINJA,
        region="Maharashtra",
    )

    body = api_client.get(reverse(URL_NAME), filters).json()

    assert body["suppressed"] is True
    assert set(body) == {"data_source", "disclaimer", "suppressed", "message"}
    assert body["data_source"] == DATA_SOURCE_LABEL
    assert body["disclaimer"] == DISCLAIMER_TEXT


def test_below_floor_rows_are_dropped_never_zeroed(api_client, make_profile):
    """D-01/D-03: the withheld row is absent from the payload entirely."""
    _seed(make_profile, count=6, current_status=CandidateProfile.Status.JOINED)
    _seed(make_profile, count=3, current_status=CandidateProfile.Status.WITHDRAWN)

    body = api_client.get(reverse(URL_NAME)).json()

    assert body["suppressed"] is False
    assert body["total_in_cohort"] == 9
    assert [row["status_group"] for row in body["results"]] == ["JOINED"]
    assert [row["candidate_count"] for row in body["results"]] == [6]
    assert all(row["candidate_count"] >= 5 for row in body["results"])
    assert "WITHDRAWN_OTHER" not in body["results"][0]["status_group"]
    # The dropped row's statuses are nowhere in the serialized payload.
    assert "WITHDRAWN" not in str(body)


def test_a_cohort_whose_every_row_is_below_floor_is_suppressed_wholesale(api_client, make_profile):
    """D-02: seven candidates, rows of four and three — the slice is not publishable."""
    _seed(make_profile, count=4, current_status=CandidateProfile.Status.REGISTERED)
    _seed(make_profile, count=3, current_status=CandidateProfile.Status.JOINED)

    body = api_client.get(reverse(URL_NAME)).json()

    assert body["suppressed"] is True
    assert set(body) == {"data_source", "disclaimer", "suppressed", "message"}


def test_unknown_filter_values_are_refused_by_name(api_client, make_profile):
    """D-12: a typo names its parameter and never gets community-wide numbers."""
    _seed(make_profile, count=6)

    for params, param in (
        ({"batch": "2019"}, "batch"),
        ({"hiring_type": "SENIOR"}, "hiring_type"),
        ({"region": "<script>"}, "region"),
    ):
        response = api_client.get(reverse(URL_NAME), params)
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_filter"
        assert response.json()["param"] == param


def test_anonymous_reads_and_writes_are_closed(api_client, make_profile):
    """04 §6: public reads; the endpoint has no write path at all."""
    _seed(make_profile, count=6)
    url = reverse(URL_NAME)

    assert api_client.get(url).status_code == 200
    assert api_client.post(url, {}).status_code == 405
    assert api_client.put(url, {}).status_code == 405
    assert api_client.delete(url).status_code == 405


def test_payload_is_attributed_disclaimed_and_stamped(api_client, make_profile):
    """ANAL-05 carries to the new endpoint (7.2 D-06)."""
    _seed(make_profile, count=6)

    body = api_client.get(reverse(URL_NAME)).json()

    assert body["data_source"] == DATA_SOURCE_LABEL
    assert body["disclaimer"] == DISCLAIMER_TEXT
    assert body["generated_at"].endswith("Z")


def test_no_candidate_identifier_can_reach_the_payload(api_client, make_profile):
    """The strongest privacy test in the app belongs on its most granular payload."""
    profiles = []
    for i in range(6):
        profile = make_profile(batch="2025", region="Maharashtra")
        profile.display_name = f"Distinctive Handle {i}"
        profile.public_identity_mode = CandidateProfile.PublicIdentityMode.DISPLAY_NAME
        profile.save(update_fields=["display_name", "public_identity_mode"])
        profiles.append(profile)

    text = api_client.get(reverse(URL_NAME)).content.decode()

    for needle in [
        *[str(profile.id) for profile in profiles],
        *[profile.user.email for profile in profiles if profile.user_id],
        "Distinctive Handle",
        "display_name",
        "email",
        "candidate_profile",
    ]:
        assert needle not in text, f"{needle!r} leaked from the status distribution"


def test_throttle_scope_is_declared_on_the_view(api_client, make_profile, monkeypatch):
    """7.2 R1: a ScopedRateThrottle whose view declares no scope is inert."""
    assert StatusDistributionView.throttle_scope == AnalyticsReadRateThrottle.scope
    assert AnalyticsReadRateThrottle in StatusDistributionView.throttle_classes

    _seed(make_profile, count=6)
    monkeypatch.setitem(AnalyticsReadRateThrottle.THROTTLE_RATES, "analytics_reads", "2/min")

    url = reverse(URL_NAME)
    assert api_client.get(url).status_code == 200
    assert api_client.get(url).status_code == 200
    assert api_client.get(url).status_code == 429


def test_cached_payload_ignores_data_added_after_the_first_read(api_client, make_profile):
    """D-04/D-05: the new endpoint rides the same payload cache as its siblings."""
    _seed(make_profile, count=6, region="Goa")

    first = api_client.get(reverse(URL_NAME), {"region": "Goa"}).json()
    _seed(make_profile, count=6, region="Goa")
    second = api_client.get(reverse(URL_NAME), {"region": "Goa"}).json()

    assert first == second
    assert second["total_in_cohort"] == 6
    # A different filter signature is a different key, so it is not the cached copy.
    assert api_client.get(reverse(URL_NAME), {"region": "Kerala"}).json()["suppressed"] is True


def test_floor_helper_is_reused_not_reimplemented():
    """Guard against a second suppression rule growing inside this endpoint."""
    assert apply_row_floor([{"candidate_count": 4}, {"candidate_count": 5}]) == [
        {"candidate_count": 5}
    ]
    assert apply_row_floor([{"candidate_count": 4}]) is None
