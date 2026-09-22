"""Moderation throttles (Phase 8.1 — MOD-03, 08 §3.3).

`ReportRateThrottle` guards report submission at 10/hour per candidate. The
scope is declared on the VIEW (`throttle_scope = "reports"`), not only here —
DRF's `ScopedRateThrottle.allow_request` reads the scope from the view and
silently allows everything when the view declares none (7.2 R1 landmine,
found on community's six write views).
"""

from rest_framework.throttling import ScopedRateThrottle


class ReportRateThrottle(ScopedRateThrottle):
    """``reports`` scope — 10/hour (settings)."""

    scope = "reports"
