"""Phase 7.2 boundary tests (7.1 D3/D4/D5, inverted deliberately).

7.1 asserted that `apps/analytics` had **no** HTTP surface and **no** caching, as a
boundary against this phase. 7.2 owns those now, so the same file asserts the
inverse — the surface exists, and what must *not* have changed still does not:

1. Still read-only: zero models, zero migrations (7.1 D3).
2. The surface 7.1 deferred now exists: views, urls, cache and the warmup task.
3. `services.py` still imports no cache module — computation stays pure and caching
   lives at the edge, so there is exactly one compute path (7.2 D-04).
4. 04 §52's `/analytics/timeline/` is still absent, on purpose (7.2 D-10).
5. No aggregation payload can be emitted without the COMMUNITY_REPORTED attribution
   and the non-affiliation disclaimer (7.1 D4, honoured through the cache).
"""

from pathlib import Path

from django.apps import apps as django_apps
from django.urls import URLPattern, URLResolver, get_resolver

import apps.analytics.services as analytics_services

ANALYTICS_DIR = Path(__file__).resolve().parent.parent


def test_no_models_or_migrations_in_analytics():
    """7.1 D3: the analytics app ships no database write models and no migrations.

    Still asserted after 7.2 added an HTTP surface, which is the point: an endpoint
    is not a reason to grow a schema.
    """
    assert not (ANALYTICS_DIR / "models.py").exists()
    assert not (ANALYTICS_DIR / "migrations").exists()
    assert list(django_apps.get_app_config("analytics").get_models()) == []


def test_http_surface_now_exists_in_analytics():
    """7.1 D5 inverted: the surface 7.1 deliberately deferred is 7.2's deliverable."""
    assert (ANALYTICS_DIR / "views.py").exists()
    assert (ANALYTICS_DIR / "urls.py").exists()
    assert (ANALYTICS_DIR / "cache.py").exists()
    assert (ANALYTICS_DIR / "tasks.py").exists()
    assert (ANALYTICS_DIR / "throttles.py").exists()
    # Payload assembly stays in services; no DRF serializer layer was added.
    assert not (ANALYTICS_DIR / "serializers.py").exists()


def test_services_layer_stays_cache_free():
    """7.2 D-04: computation is pure; caching happens at the edge."""
    with open(analytics_services.__file__, encoding="utf-8") as f:
        source = f.read()
    assert "django.core.cache" not in source
    assert "cache_page" not in source
    assert "from apps.analytics import cache" not in source


def test_timeline_analytics_route_is_absent():
    """7.2 D-10: 04 §52 is a recorded gap, so the route must not appear by accident."""
    names = _url_names(get_resolver())
    assert "analytics-overview" in names
    assert "analytics-batches" in names
    assert "analytics-hiring-types" in names
    assert "analytics-regions" in names
    assert "public-stats" in names
    assert not [name for name in names if name and "timeline" in name and "analytics" in name]


def _url_names(resolver) -> set[str | None]:
    names: set[str | None] = set()
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            names |= _url_names(pattern)
        elif isinstance(pattern, URLPattern):
            names.add(pattern.name)
    return names


def test_attribution_and_disclaimer_are_mandatory_on_every_payload():
    """7.1 D4: even the smallest cohort's response is attributed and disclaimed."""
    suppressed, payload = analytics_services.check_privacy_suppression(0)

    assert suppressed is True
    assert payload is not None
    assert payload["data_source"] == "COMMUNITY_REPORTED"
    assert payload["disclaimer"] == (
        "These figures are based on community-submitted data and are not official TCS statistics."
    )
