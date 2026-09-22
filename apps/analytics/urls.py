"""Analytics routes (Phase 7.2): /api/v1/analytics/* and /api/v1/public/stats/.

Included from `config/urls.py` under the shared `/api/v1/` prefix, so
`public/stats/` here resolves to 04 §80's documented `/api/v1/public/stats/`
without a second URL module.

04 §52's `/analytics/timeline/` is deliberately absent — deferred by 7.2 D-10 and
recorded as a known gap (no ANAL requirement owns it).
"""

from django.urls import path

from apps.analytics.views import (
    AnalyticsBatchView,
    AnalyticsHiringTypeView,
    AnalyticsOverviewView,
    AnalyticsRegionView,
    PublicStatsView,
)

urlpatterns = [
    path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("analytics/batches/", AnalyticsBatchView.as_view(), name="analytics-batches"),
    path(
        "analytics/hiring-types/",
        AnalyticsHiringTypeView.as_view(),
        name="analytics-hiring-types",
    ),
    path("analytics/regions/", AnalyticsRegionView.as_view(), name="analytics-regions"),
    path("public/stats/", PublicStatsView.as_view(), name="public-stats"),
]
