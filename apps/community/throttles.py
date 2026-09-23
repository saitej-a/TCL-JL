"""Community throttles (04 §41/§42; plan 05-02 R7; 9.3 D1).

Writes share one scoped bucket guarding every community write (post create/edit,
comment create, vote, lock/unlock, pin/unpin). Reads stay unthrottled for
signed-in candidates — the community's value is browsing, and 04 §9's global
pagination already caps any single response — but the **anonymous** read surface
opened by 9.3 D1 is bounded: an unauthenticated scraper faces a per-IP bucket,
not an open door.

**The scope must also be declared on the view** (`throttle_scope`). DRF's
`ScopedRateThrottle.allow_request` does `self.scope = getattr(view,
'throttle_scope', None)` and returns `True` — allowing the request — when the view
declares none, so a class-level `scope` alone is inert (7.2 R1; the same trap the
analytics and reports scopes document).
"""

from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class CommunityWriteRateThrottle(ScopedRateThrottle):
    """``community_writes`` scope — 30/min (settings)."""

    scope = "community_writes"


class CommunityAnonReadRateThrottle(SimpleRateThrottle):
    """Per-IP bucket for the anonymous community read surface (9.3 D1).

    ScopedRateThrottle is the wrong shape here: the throttle must apply ONLY to
    unauthenticated callers (signed-in candidates keep 5.2's unthrottled
    browsing contract), which `get_throttles()` decides per request by including
    this class only when `request.user.is_authenticated` is false. A
    SimpleRateThrottle keyed on IP gives each visitor its own bucket with no
    view-scope wiring — and therefore no inert-scope failure mode to guard.
    """

    scope = "community_anon_reads"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
