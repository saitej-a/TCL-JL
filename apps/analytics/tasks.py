"""Celery task for the hourly analytics cache warmup (Phase 7.2, D-07).

The task name byte-matches both the beat entry reserved in `config/celery.py`
(`warm-analytics-cache-hourly` -> `:45`) and `CELERY_TASK_ROUTES` in
`config/settings/base.py`, which routes it to the `maintenance` queue beside
`notifications.tasks.prune_stale_devices`.

A decorator `name=` that disagrees with the route silently sends the task to
`default` instead (the 6.2 lesson), which is why the name is asserted by tests.
"""

from __future__ import annotations

import logging

from celery import shared_task

from apps.analytics.cache import get_cache_ttl, store_payload, warm_targets

logger = logging.getLogger("analytics")


@shared_task(name="analytics.tasks.warm_analytics_cache", queue="maintenance")
def warm_analytics_cache() -> int:
    """Refresh every unfiltered default analytics payload; return how many.

    This *refreshes* rather than fills-if-missing: overwriting the hot keys is what
    bounds staleness to roughly the beat cadence, while the TTL
    (`ANALYTICS_CACHE_TTL`) remains the backstop that survives a missed run
    (D-05). Warming the unfiltered default of every cached endpoint costs about the
    same as warming only overview + batch and leaves no cold default behind.

    Returns:
        The number of payloads refreshed.
    """
    warmed = 0
    for endpoint, builder in warm_targets():
        store_payload(endpoint, builder())
        warmed += 1

    logger.info(
        "WARMED_ANALYTICS_CACHE: endpoints=%d ttl=%ds",
        warmed,
        get_cache_ttl(),
    )
    return warmed
