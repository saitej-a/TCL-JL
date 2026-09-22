"""Cache and warmup tests (Phase 7.2, D-04/D-05/D-06/D-07).

The cache is asserted through its observable behaviour — a second read that ignores
new data, keys that do not collide across filters, a `generated_at` that does not
move on a hit — rather than by poking at backend internals.
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from apps.analytics.cache import (
    ENDPOINT_BATCHES,
    ENDPOINT_OVERVIEW,
    analytics_cache_key,
    cached_payload,
    get_cache_ttl,
    warm_targets,
)
from apps.analytics.services import get_community_overview_stats

pytestmark = pytest.mark.django_db


def _seed(make_profile, count: int = 6, **kwargs):
    return [make_profile(**kwargs) for _ in range(count)]


def test_second_read_is_served_from_the_cache(api_client, make_profile):
    _seed(make_profile)
    url = reverse("analytics-overview")

    first = api_client.get(url).json()
    assert first["total_candidates"] == 6

    # Change the data; a cached response must not notice.
    _seed(make_profile, count=5)

    second = api_client.get(url).json()
    assert second == first
    assert second["total_candidates"] == 6


def test_generated_at_survives_a_cache_hit(api_client, make_profile):
    """D-06: a hit reports when its numbers were computed, not when it was served."""
    _seed(make_profile)
    url = reverse("analytics-overview")

    first = api_client.get(url).json()
    second = api_client.get(url).json()

    assert first["generated_at"] == second["generated_at"]


def test_cache_keys_do_not_collide_across_filters(api_client, make_profile):
    _seed(make_profile, region="Goa")
    _seed(make_profile, count=7, batch="2026", region="Kerala")

    unfiltered = api_client.get(reverse("analytics-batches")).json()
    filtered = api_client.get(reverse("analytics-batches"), {"region": "goa"}).json()
    other = api_client.get(reverse("analytics-batches"), {"region": "kerala"}).json()

    assert unfiltered["total_in_cohort"] == 13
    assert filtered["total_in_cohort"] == 6
    assert other["total_in_cohort"] == 7
    assert len({unfiltered["total_in_cohort"], filtered["total_in_cohort"]}) == 2

    assert analytics_cache_key(ENDPOINT_BATCHES) != analytics_cache_key(
        ENDPOINT_BATCHES, region="goa"
    )


def test_absent_filters_share_the_default_key():
    """An empty filter and an omitted filter are the same request, so one entry."""
    assert analytics_cache_key(ENDPOINT_BATCHES, region=None) == analytics_cache_key(
        ENDPOINT_BATCHES
    )
    assert analytics_cache_key(ENDPOINT_BATCHES, region="goa") == analytics_cache_key(
        ENDPOINT_BATCHES, region="goa"
    )


def test_cached_payload_builder_runs_once():
    calls = []

    def builder():
        calls.append(1)
        return {"data_source": "COMMUNITY_REPORTED", "hit": len(calls)}

    first = cached_payload(ENDPOINT_OVERVIEW, builder)
    second = cached_payload(ENDPOINT_OVERVIEW, builder)

    # Equal, not identical: the backend round-trips the payload through its
    # serializer, so the cached copy is a separate object with the same content.
    assert first == second
    assert len(calls) == 1


def test_ttl_is_read_from_settings():
    assert get_cache_ttl() == 7200
    with override_settings(ANALYTICS_CACHE_TTL=42):
        assert get_cache_ttl() == 42


def test_warmup_covers_every_endpoint_without_filters(make_profile):
    """D-07: the warmup leaves no cold default behind."""
    _seed(make_profile)

    endpoints = [endpoint for endpoint, _ in warm_targets()]
    assert endpoints == ["overview", "batches", "hiring-types", "regions", "public-stats"]

    # Nothing is stored until the task (or a request) actually builds a payload.
    for endpoint, _ in warm_targets():
        assert cache.get(analytics_cache_key(endpoint)) is None


def test_warm_analytics_cache_populates_every_default_key(make_profile):
    from apps.analytics.tasks import warm_analytics_cache

    _seed(make_profile)

    assert warm_analytics_cache() == 5

    for endpoint, _ in warm_targets():
        payload = cache.get(analytics_cache_key(endpoint))
        assert payload is not None
        assert payload["data_source"] == "COMMUNITY_REPORTED"
        assert payload["disclaimer"]


def test_warm_analytics_cache_refreshes_rather_than_fills(make_profile):
    """D-05: the hourly run bounds staleness by overwriting the hot keys."""
    from apps.analytics.tasks import warm_analytics_cache

    _seed(make_profile)
    stale = get_community_overview_stats()
    cached_payload(ENDPOINT_OVERVIEW, get_community_overview_stats)
    assert cache.get(analytics_cache_key(ENDPOINT_OVERVIEW)) == stale

    _seed(make_profile, count=5)
    warm_analytics_cache()

    refreshed = cache.get(analytics_cache_key(ENDPOINT_OVERVIEW))
    assert refreshed["total_candidates"] == 11


def test_warmup_task_name_matches_the_reserved_route_and_beat_entry():
    """D-07: a name that disagrees with the route silently lands on `default`.

    Checked against all three places the name has to agree: the task decorator, the
    settings route, and `config/celery.py`'s reserved beat entry.
    """
    from apps.analytics.tasks import warm_analytics_cache
    from config.celery import app

    expected = "analytics.tasks.warm_analytics_cache"
    assert warm_analytics_cache.name == expected
    assert settings.CELERY_TASK_ROUTES[expected] == {"queue": "maintenance"}
    beat_tasks = {entry["task"] for entry in app.conf.beat_schedule.values()}
    assert expected in beat_tasks
