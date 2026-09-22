"""Payload-level analytics cache (Phase 7.2, D-04/D-05).

The cached unit is the **assembled response payload**, keyed per endpoint + filter
signature (D-04). That keeps `apps/analytics/services.py` the single compute path —
there is no second, snapshot-based assembly path to drift away from it.

Django's cache framework only, never a raw Redis client (the 6.2 D3 precedent):
the suite keeps running on `LocMemCache` with no Redis required, and the Redis
backend in dev/prod is a settings concern rather than a code one.

Caching lives here rather than in `services.py` so the service layer stays pure
computation; that separation is asserted by `test_phase_boundary.py`.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("analytics")

# Endpoint slugs, shared by the views, the cache and the warmup task so a key
# written by one can always be found by the others.
ENDPOINT_OVERVIEW = "overview"
ENDPOINT_BATCHES = "batches"
ENDPOINT_HIRING_TYPES = "hiring-types"
ENDPOINT_REGIONS = "regions"
ENDPOINT_PUBLIC_STATS = "public-stats"

# Bumped when a payload shape changes: a versioned prefix means a deploy can never
# serve a payload cached by older code (7.2 discretion).
CACHE_KEY_VERSION = "v1"


def get_cache_ttl() -> int:
    """TTL in seconds, read at call time so ops can tune it without a deploy."""
    return getattr(settings, "ANALYTICS_CACHE_TTL", 7200)


def analytics_cache_key(endpoint: str, **filters: str | None) -> str:
    """Build a stable, order-independent cache key.

    Filters are sorted before hashing and empty values are dropped, so `/batches/`
    and `/batches/?region=` share one key instead of minting a second entry for
    every cosmetic variation — the same reasoning behind D-12's normalization.
    """
    signature = "&".join(f"{name}={filters[name]}" for name in sorted(filters) if filters[name])
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
    return f"analytics:{CACHE_KEY_VERSION}:{endpoint}:{digest}"


def store_payload(endpoint: str, payload: dict[str, Any], **filters: str | None) -> str:
    """Write a payload to the cache and return the key it was stored under."""
    key = analytics_cache_key(endpoint, **filters)
    cache.set(key, payload, get_cache_ttl())
    return key


def cached_payload(
    endpoint: str,
    builder: Callable[[], dict[str, Any]],
    **filters: str | None,
) -> dict[str, Any]:
    """Read-through cache around `builder` (D-04).

    The payload is built — and its `generated_at` stamped — only on a miss, so a
    cache hit reports when its numbers were **computed** rather than when it was
    served (D-06).
    """
    key = analytics_cache_key(endpoint, **filters)
    payload = cache.get(key)
    if payload is not None:
        return payload

    payload = builder()
    cache.set(key, payload, get_cache_ttl())
    logger.debug("ANALYTICS_CACHE_MISS: warmed key=%s", key)
    return payload


def warm_targets() -> list[tuple[str, Callable[[], dict[str, Any]]]]:
    """The unfiltered default payloads the hourly warmup refreshes (D-07).

    Local import keeps the task module free of an import cycle back through the
    views' URL wiring.
    """
    from apps.analytics import services

    return [
        (ENDPOINT_OVERVIEW, services.get_community_overview_stats),
        (ENDPOINT_BATCHES, services.get_batch_breakdown),
        (ENDPOINT_HIRING_TYPES, services.get_hiring_type_breakdown),
        (ENDPOINT_REGIONS, services.get_region_breakdown),
        (ENDPOINT_PUBLIC_STATS, services.get_public_stats),
    ]
