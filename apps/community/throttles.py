"""Community throttle (04 §41/§42; plan 05-02 R7).

One scoped bucket guards every community write (post create/edit, comment
create, vote, lock/unlock, pin/unpin). Read routes stay unthrottled — the
community's value is browsing, and 04 §9's global pagination already caps any
single response.
"""

from rest_framework.throttling import ScopedRateThrottle


class CommunityWriteRateThrottle(ScopedRateThrottle):
    """``community_writes`` scope — 30/min (settings)."""

    scope = "community_writes"
