"""Root-level views: service status + health probes (T1.7).

`/health/` answers liveness — process is up, no dependency I/O (safe to keep
answering when a dependency blips; it must not flap during restarts).

`/health/ready/` answers readiness — pings PostgreSQL and Redis; any failure
degrades to 503 with the failing component named. This endpoint backs the
container healthchecks in both compose files.
"""

import json

from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, JsonResponse


def index(request) -> HttpResponse:
    """Minimal root endpoint identifying the service (API routes land in later phases)."""
    body = json.dumps({"service": "tcs-joining-tracker", "status": "ok", "phase": "1.2"})
    return HttpResponse(body, content_type="application/json")


def health(request) -> JsonResponse:
    """Liveness probe: process reachable, zero dependency checks."""
    return JsonResponse({"status": "alive"})


def _check_database() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _check_cache() -> None:
    """Real round-trip through the configured cache backend (redis in dev/prod)."""
    cache.set("_healthcheck", "1", 5)
    if cache.get("_healthcheck") != "1":
        raise RuntimeError("cache round-trip failed")


def health_ready(request) -> JsonResponse:
    """Readiness probe: 200 only when PostgreSQL and Redis answer; 503 otherwise."""
    checks = {"database": _check_database, "cache": _check_cache}
    results: dict[str, str] = {}
    healthy = True
    for name, probe in checks.items():
        try:
            probe()
            results[name] = "ok"
        except Exception as exc:  # noqa: BLE001 — a probe failure is the payload, not a bug
            healthy = False
            results[name] = f"down: {exc.__class__.__name__}"
    return JsonResponse(
        {"status": "ok" if healthy else "not_ready", **results},
        status=200 if healthy else 503,
    )
