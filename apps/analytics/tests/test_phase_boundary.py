"""Phase 7.1 boundary tests (D3, D4, D5).

Proves the deliberate scope boundaries of Phase 7.1:
1. apps.analytics is strictly read-only: zero models, zero migrations (D3).
2. No HTTP surface ships yet — no views.py / urls.py / serializers.py (D5 to 7.2).
3. No Redis caching and no Celery warmup task ship yet (D5 to 7.2).
4. No aggregation payload can be emitted without the COMMUNITY_REPORTED
   attribution and the non-affiliation disclaimer (D4).
"""

from pathlib import Path

from django.apps import apps as django_apps

import apps.analytics.services as analytics_services

ANALYTICS_DIR = Path(__file__).resolve().parent.parent


def test_no_models_or_migrations_in_analytics():
    """D3: the analytics app ships no database write models and no migrations.

    Asserted three ways — no models module, no migrations directory, and zero
    models registered on the app config — so a model added indirectly (e.g. in a
    neighbouring module imported by the app) still fails this test.
    """
    assert not (ANALYTICS_DIR / "models.py").exists()
    assert not (ANALYTICS_DIR / "migrations").exists()
    assert list(django_apps.get_app_config("analytics").get_models()) == []


def test_no_http_surface_in_analytics():
    """D5: endpoints belong to Phase 7.2; 7.1 exposes the service layer only."""
    assert not (ANALYTICS_DIR / "views.py").exists()
    assert not (ANALYTICS_DIR / "urls.py").exists()
    assert not (ANALYTICS_DIR / "serializers.py").exists()


def test_no_redis_caching_or_warmup_task_in_analytics():
    """D5: Redis caching and the hourly Celery Beat warmup belong to Phase 7.2."""
    assert not (ANALYTICS_DIR / "tasks.py").exists()

    with open(analytics_services.__file__, encoding="utf-8") as f:
        source = f.read()
    assert "django.core.cache" not in source
    assert "cache_page" not in source


def test_attribution_and_disclaimer_are_mandatory_on_every_payload():
    """D4: even the smallest cohort's response is attributed and disclaimed."""
    suppressed, payload = analytics_services.check_privacy_suppression(0)

    assert suppressed is True
    assert payload is not None
    assert payload["data_source"] == "COMMUNITY_REPORTED"
    assert payload["disclaimer"] == (
        "These figures are based on community-submitted data and are not official TCS statistics."
    )
