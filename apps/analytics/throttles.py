"""Analytics read throttle (Phase 7.2, D-11).

These are the app's most expensive read paths and they are public, so unlike the
community's read routes they are throttled: cache keys multiply per filter
combination, which means an anonymous caller can walk region x hiring_type x batch
and force uncached computation of every aggregate query on each request.

**The scope must also be declared on the view** (`throttle_scope`). DRF's
`ScopedRateThrottle.allow_request` does `self.scope = getattr(view,
'throttle_scope', None)` and returns `True` — allowing the request — when the view
declares none, so a class-level `scope` alone is inert. `AnalyticsReadView` sets
both from this class, and `test_endpoints.py` proves the bucket actually engages
rather than trusting that it does.
"""

from rest_framework.throttling import ScopedRateThrottle


class AnalyticsReadRateThrottle(ScopedRateThrottle):
    """``analytics_reads`` scope — 120/min (settings), keyed per IP when anonymous."""

    scope = "analytics_reads"
