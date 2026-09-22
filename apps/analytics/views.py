"""Thin anonymous views over the analytics service layer (Phase 7.2).

Covers 04 §47-§53 (``/api/v1/analytics/*``) and 04 §80
(``/api/v1/public/stats/``). Anonymous by spec, not by choice: §6 lists
"Landing-page information" and "Public aggregate statistics" under the Anonymous
authorization level, and there is no owner to scope by — the data is aggregate.

Views stay thin (the 5.2/6.2 pattern): validation and invariants live in
`services.py`, caching in `cache.py`, and these classes only translate the domain
error into an HTTP code.
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics import services
from apps.analytics.cache import (
    ENDPOINT_BATCHES,
    ENDPOINT_HIRING_TYPES,
    ENDPOINT_OVERVIEW,
    ENDPOINT_PUBLIC_STATS,
    ENDPOINT_REGIONS,
    cached_payload,
)
from apps.analytics.throttles import AnalyticsReadRateThrottle

# Error envelope for a rejected filter (7.2 D-12). The param is named so a client
# can point at the offending query string; the alternative — silently ignoring an
# unknown value — would answer a typo with confidently wrong community-wide data
# on a public stats page.
INVALID_FILTER_CODE = "invalid_filter"


class AnalyticsReadView(APIView):
    """Base class for the anonymous analytics reads.

    Subclasses declare the endpoint slug (their cache namespace) and which query
    parameters they actually consume, so a filter is only ever validated for an
    endpoint that reads it and an undocumented parameter is ignored rather than
    answered with a 400 the spec never promised.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnalyticsReadRateThrottle]
    # ScopedRateThrottle reads the scope off the view; see throttles.py.
    throttle_scope = AnalyticsReadRateThrottle.scope

    endpoint: str = ""
    accepted_filters: tuple[str, ...] = ()

    def build(self, **filters: str) -> dict[str, Any]:
        """Return the service payload for this endpoint (implemented by subclasses)."""
        raise NotImplementedError

    def get(self, request):
        try:
            filters = services.validate_filters(
                **{name: request.query_params.get(name) for name in self.accepted_filters}
            )
        except services.InvalidAnalyticsFilter as exc:
            return Response(
                {
                    "error": INVALID_FILTER_CODE,
                    "detail": str(exc),
                    "param": exc.param,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        def builder() -> dict[str, Any]:
            return self.build(**filters)

        return Response(cached_payload(self.endpoint, builder, **filters))


class AnalyticsOverviewView(AnalyticsReadView):
    """`GET /api/v1/analytics/overview/` (04 §48) — counts plus both wait-time baselines."""

    endpoint = ENDPOINT_OVERVIEW
    accepted_filters = ()

    def build(self, **filters: str) -> dict[str, Any]:
        return services.get_community_overview_stats()


class AnalyticsBatchView(AnalyticsReadView):
    """`GET /api/v1/analytics/batches/` (04 §49) — `?hiring_type=&region=`."""

    endpoint = ENDPOINT_BATCHES
    accepted_filters = ("hiring_type", "region")

    def build(self, **filters: str) -> dict[str, Any]:
        return services.get_batch_breakdown(**filters)


class AnalyticsHiringTypeView(AnalyticsReadView):
    """`GET /api/v1/analytics/hiring-types/` (04 §50) — `?batch=&region=`."""

    endpoint = ENDPOINT_HIRING_TYPES
    accepted_filters = ("batch", "region")

    def build(self, **filters: str) -> dict[str, Any]:
        return services.get_hiring_type_breakdown(**filters)


class AnalyticsRegionView(AnalyticsReadView):
    """`GET /api/v1/analytics/regions/` (04 §51) — `?batch=&hiring_type=`."""

    endpoint = ENDPOINT_REGIONS
    accepted_filters = ("batch", "hiring_type")

    def build(self, **filters: str) -> dict[str, Any]:
        return services.get_region_breakdown(**filters)


class PublicStatsView(AnalyticsReadView):
    """`GET /api/v1/public/stats/` (04 §80) — the landing page's KPI counters.

    Takes no filters, so its cache key is a single entry: the highest-volume
    anonymous endpoint in the app still costs one cached read per TTL.
    """

    endpoint = ENDPOINT_PUBLIC_STATS
    accepted_filters = ()

    def build(self, **filters: str) -> dict[str, Any]:
        return services.get_public_stats()
