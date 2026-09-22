"""HTTP contract tests for the analytics endpoints (Phase 7.2; 04 §47-§53, §80).

Carries 04 §108's seven required test names plus the 7.2 decisions that have no
home in the service tests: anonymous access (D-08), the landing-stats shape (D-09),
filter validation as HTTP 400 (D-12), and a throttle that actually engages (D-11).
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.urls import reverse

from apps.analytics.services import (
    BASELINE_OFFER_LETTER,
    BASELINE_READINESS_SURVEY,
    DATA_SOURCE_LABEL,
    DISCLAIMER_TEXT,
)
from apps.analytics.throttles import AnalyticsReadRateThrottle
from apps.analytics.views import (
    AnalyticsBatchView,
    AnalyticsHiringTypeView,
    AnalyticsOverviewView,
    AnalyticsRegionView,
    PublicStatsView,
)
from apps.candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db

ALL_ENDPOINTS = (
    "analytics-overview",
    "analytics-batches",
    "analytics-hiring-types",
    "analytics-regions",
    "public-stats",
)


def _seed_cohort(make_profile, batch: str = "2025", hiring_type=None, region: str = "Maharashtra"):
    """Six candidates, which clears the `<5` floor at both slice and row level."""
    kwargs = {"batch": batch, "region": region}
    if hiring_type is not None:
        kwargs["hiring_type"] = hiring_type
    return [make_profile(**kwargs) for _ in range(6)]


def test_overview_analytics(api_client, make_profile):
    """04 §48: anonymous overview with counts, attribution and both baselines."""
    for _ in range(6):
        make_profile(
            batch="2025", current_status=CandidateProfile.Status.WAITING_FOR_JOINING_LETTER
        )
    for _ in range(4):
        make_profile(batch="2025", current_status=CandidateProfile.Status.JOINED)

    response = api_client.get(reverse("analytics-overview"))

    assert response.status_code == 200
    body = response.json()
    assert body["total_candidates"] == 10
    assert body["waiting_for_joining_letter"] == 6
    assert body["joining_letters_reported"] == 4
    assert body["joined_reported"] == 4
    assert body["generated_at"].endswith("Z")
    # D-13/D-14: both wait-time metrics ride the overview payload.
    assert set(body["wait_times"]) == {
        "offer_to_joining_letter",
        "survey_to_joining_letter",
    }


def test_batch_analytics(api_client, make_profile):
    """04 §49: batch rows, and `?hiring_type=` actually filters."""
    for _ in range(6):
        make_profile(batch="2024", hiring_type=CandidateProfile.HiringType.DIGITAL)
    for _ in range(6):
        make_profile(batch="2025", hiring_type=CandidateProfile.HiringType.NINJA)

    body = api_client.get(reverse("analytics-batches")).json()
    assert body["total_in_cohort"] == 12
    assert {row["batch"] for row in body["results"]} == {"2024", "2025"}

    filtered = api_client.get(reverse("analytics-batches"), {"hiring_type": "DIGITAL"}).json()
    assert filtered["total_in_cohort"] == 6
    assert [row["batch"] for row in filtered["results"]] == ["2024"]


def test_hiring_type_analytics(api_client, make_profile):
    """04 §50: stream breakdown, and `?batch=` actually filters."""
    for _ in range(6):
        make_profile(batch="2025", hiring_type=CandidateProfile.HiringType.PRIME)
    for _ in range(6):
        make_profile(batch="2024", hiring_type=CandidateProfile.HiringType.NINJA)

    body = api_client.get(reverse("analytics-hiring-types")).json()
    assert {row["hiring_type"] for row in body["results"]} == {"PRIME", "NINJA"}

    filtered = api_client.get(reverse("analytics-hiring-types"), {"batch": "2024"}).json()
    assert [row["hiring_type"] for row in filtered["results"]] == ["NINJA"]


def test_region_analytics(api_client, make_profile):
    """04 §51: regional distribution."""
    for _ in range(5):
        make_profile(region="Telangana")
    for _ in range(7):
        make_profile(region="Karnataka")

    body = api_client.get(reverse("analytics-regions")).json()
    assert body["total_in_cohort"] == 12
    counts = {row["region"]: row["candidate_count"] for row in body["results"]}
    assert counts == {"Telangana": 5, "Karnataka": 7}


def test_minimum_group_suppression(api_client, make_profile):
    """7.2 D-01/D-02 over HTTP: a small slice suppresses, a small row disappears."""
    for _ in range(4):
        make_profile(batch="2025", region="Goa")

    suppressed = api_client.get(reverse("analytics-regions"), {"batch": "2024"}).json()
    assert suppressed["suppressed"] is True
    assert set(suppressed) == {"data_source", "disclaimer", "suppressed", "message"}

    # Slice of 11 clears the floor, but the 4-candidate batch row must not appear.
    for _ in range(7):
        make_profile(batch="2026", region="Kerala")

    body = api_client.get(reverse("analytics-batches")).json()
    assert body["suppressed"] is False
    assert body["total_in_cohort"] == 11
    assert [row["batch"] for row in body["results"]] == ["2026"]
    assert all(row["candidate_count"] >= 5 for row in body["results"])


def test_private_fields_not_in_analytics(api_client, make_profile):
    """No candidate identifier, email or display name can appear in any response."""
    profiles = []
    for i in range(6):
        profile = make_profile(
            batch="2025",
            region="Maharashtra",
        )
        profile.display_name = f"Distinctive Handle {i}"
        profile.public_identity_mode = CandidateProfile.PublicIdentityMode.DISPLAY_NAME
        profile.save(update_fields=["display_name", "public_identity_mode"])
        profiles.append(profile)

    leaked = [
        *[str(p.id) for p in profiles],
        *[p.user.email for p in profiles if p.user_id],
        "Distinctive Handle",
        "display_name",
        "email",
    ]

    for name in ALL_ENDPOINTS:
        text = api_client.get(reverse(name)).content.decode()
        for needle in leaked:
            assert needle not in text, f"{needle!r} leaked from {name}"


def test_analytics_marked_community_reported(api_client, make_profile):
    """ANAL-05: every response, suppressed or not, is attributed and disclaimed."""
    _seed_cohort(make_profile)
    # A second, tiny cohort so the suppressed branch is exercised over HTTP too.
    for _ in range(2):
        make_profile(batch="2026")

    for name in ALL_ENDPOINTS:
        response = api_client.get(reverse(name))
        assert response.status_code == 200
        body = response.json()
        assert body["data_source"] == DATA_SOURCE_LABEL
        assert body["disclaimer"] == DISCLAIMER_TEXT

    # `/regions/` accepts `batch`/`hiring_type` (04 §51 documents no region filter),
    # so the suppressed branch is reached through a slice it does accept.
    suppressed = api_client.get(reverse("analytics-regions"), {"batch": "2026"}).json()
    assert suppressed["suppressed"] is True
    assert suppressed["data_source"] == DATA_SOURCE_LABEL
    assert suppressed["disclaimer"] == DISCLAIMER_TEXT


def test_public_stats_endpoint(api_client, make_profile):
    """04 §80 / D-09: the landing counters are their own shape, not the overview."""
    _seed_cohort(make_profile)

    body = api_client.get(reverse("public-stats")).json()
    assert body["registered_candidates"] == 6
    assert body["community_posts"] == 0
    assert body["timeline_events"] == 0
    assert body["data_source"] == DATA_SOURCE_LABEL
    assert body["disclaimer"] == DISCLAIMER_TEXT
    assert body["generated_at"].endswith("Z")
    # §80's keys are not the analytics overview's keys.
    assert "total_candidates" not in body
    assert "waiting_for_joining_letter" not in body


def test_public_stats_counts_posts_and_events(api_client, make_profile, make_timeline_event):
    from datetime import date

    from apps.community.models import Post

    profiles = _seed_cohort(make_profile)
    for profile in profiles[:3]:
        make_timeline_event(profile, "JOINING_LETTER", date(2025, 6, 1))
    Post.objects.create(
        author=profiles[0].user,
        title="Joining letter batch 2025",
        body="Anyone else still waiting?",
        category="JOINING_LETTER",
    )

    body = api_client.get(reverse("public-stats")).json()
    assert body["community_posts"] == 1
    assert body["timeline_events"] == 3


def test_overview_exposes_both_wait_time_baselines(api_client, make_profile, make_timeline_event):
    """D-13: the requirement's literal baseline ships alongside 7.1 D1's."""
    from datetime import date

    for i in range(6):
        profile = make_profile(batch="2025")
        make_timeline_event(profile, "OFFER_LETTER", date(2025, 1, 1))
        make_timeline_event(profile, "JOINING_LETTER", date(2025, 3, 1 + i))
    for i in range(5):
        profile = make_profile(batch="2025")
        make_timeline_event(profile, "READINESS_SURVEY", date(2025, 2, 1))
        make_timeline_event(profile, "JOINING_LETTER", date(2025, 3, 10 + i))

    wait_times = api_client.get(reverse("analytics-overview")).json()["wait_times"]

    offer = wait_times["offer_to_joining_letter"]
    survey = wait_times["survey_to_joining_letter"]
    assert offer["baseline"] == BASELINE_OFFER_LETTER
    assert survey["baseline"] == BASELINE_READINESS_SURVEY
    assert offer["sample_size"] == 6
    assert survey["sample_size"] == 5
    # D-16: the disclosure is per source, so a fallback-heavy sample is visible.
    assert offer["baseline_source_counts"]["OFFER_LETTER_EVENT"] == 6
    assert survey["baseline_source_counts"]["READINESS_SURVEY_EVENT"] == 5


def test_unknown_filter_returns_400(api_client, make_profile):
    """D-12: a typo is refused, never answered with community-wide numbers."""
    _seed_cohort(make_profile)

    response = api_client.get(reverse("analytics-batches"), {"hiring_type": "SENIOR"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_filter"
    assert body["param"] == "hiring_type"

    assert api_client.get(reverse("analytics-hiring-types"), {"batch": "2019"}).status_code == 400
    assert api_client.get(reverse("analytics-regions"), {"hiring_type": "nope"}).status_code == 400
    # A free-text region is bounded by length/charset, not by a vocabulary (3.1 D3).
    assert api_client.get(reverse("analytics-batches"), {"region": "<script>"}).status_code == 400


def test_filters_share_one_cache_key_across_case_variations(api_client, make_profile):
    """D-12 normalization: `?region=Goa` and `?region=goa` cannot mint two entries."""
    for _ in range(6):
        make_profile(region="Goa")

    upper = api_client.get(reverse("analytics-batches"), {"region": "Goa"}).json()
    lower = api_client.get(reverse("analytics-batches"), {"region": "goa"}).json()
    padded = api_client.get(reverse("analytics-batches"), {"region": "  goa  "}).json()

    assert upper == lower == padded


def test_analytics_read_throttle_is_registered_and_engages(api_client, make_profile, monkeypatch):
    """D-11: the scope is declared on the views *and* the bucket actually engages.

    The static half matters because DRF's `ScopedRateThrottle` silently allows
    every request when the view declares no `throttle_scope`, so a class-level
    `scope` alone is inert.
    """
    assert "analytics_reads" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for view_cls in (
        AnalyticsOverviewView,
        AnalyticsBatchView,
        AnalyticsHiringTypeView,
        AnalyticsRegionView,
        PublicStatsView,
    ):
        assert view_cls.throttle_scope == AnalyticsReadRateThrottle.scope
        assert AnalyticsReadRateThrottle in view_cls.throttle_classes

    _seed_cohort(make_profile)
    monkeypatch.setitem(AnalyticsReadRateThrottle.THROTTLE_RATES, "analytics_reads", "2/min")

    url = reverse("analytics-overview")
    assert api_client.get(url).status_code == 200
    assert api_client.get(url).status_code == 200
    assert api_client.get(url).status_code == 429
