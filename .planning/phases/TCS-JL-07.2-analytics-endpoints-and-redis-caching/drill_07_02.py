"""Stage 2 live drill for Phase 7.2 (run inside the web container).

7.2 is the phase that puts 7.1's service layer behind HTTP, so unlike 7.1's drill
this one goes through the **real URLconf and the real cache** with Django's test
client — a request path, not a function call. It seeds a synthetic cohort into the
real dev database, proves the endpoint contract, and cleans every row up after
itself, re-warming the cache from the restored baseline so no payload survives that
was computed from drill data.

What it proves:
1. All five endpoints answer anonymously (04 §6) with 04 §48-§51/§80 shapes.
2. Every response carries COMMUNITY_REPORTED + the non-affiliation disclaimer,
   including through the cache (ANAL-05).
3. The `<5` floor applies per result row and at slice level (7.2 D-01/D-02).
4. Filters are whitelist-validated with a 400 that names the parameter (D-12).
5. Payloads are cached, hits keep their original `generated_at` (D-04/D-06), and
   the warmup refreshes them (D-05/D-07).
6. 04 §52's `/analytics/timeline/` is absent (D-10), and no candidate identity
   leaks into any response.
7. Cleanup returns the database to its exact baseline counts.

Usage: docker compose exec -T web python .planning/phases/<this>/drill_07_02.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid as uuidlib
from datetime import date

sys.path.insert(0, os.path.abspath("."))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.core.cache import cache  # noqa: E402
from django.test import Client  # noqa: E402

from apps.analytics.cache import (  # noqa: E402
    analytics_cache_key,
    get_cache_ttl,
    warm_targets,
)
from apps.analytics.tasks import warm_analytics_cache  # noqa: E402
from apps.candidates.models import CandidateProfile  # noqa: E402
from apps.timeline.models import TimelineEvent  # noqa: E402

STAMP = uuidlib.uuid4().hex[:8]
MAIN_REGION = f"DRILL-7-2-MAIN-{STAMP}"
SMALL_REGION = f"DRILL-7-2-SMALL-{STAMP}"
BIG_BATCH = "2025"
SMALL_BATCH = "2026"
BASE_DAY = date(2026, 2, 1)

DIGITAL = CandidateProfile.HiringType.DIGITAL
WAITING = CandidateProfile.Status.WAITING_FOR_JOINING_LETTER
JL_RECEIVED = CandidateProfile.Status.JOINING_LETTER_RECEIVED

# local.py ALLOWED_HOSTS is localhost/127.0.0.1/nginx/web — the test client's
# default SERVER_NAME ("testserver") would be rejected.
client = Client(SERVER_NAME="localhost")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def get(path: str, **params):
    return client.get(path, params)


def purge_analytics_cache() -> None:
    """Drop every cached analytics payload, touching nothing else in the cache.

    Scoped deliberately: `SESSION_ENGINE` is the cache too, so `cache.clear()` here
    would log every dev session out. `delete_pattern` is a django-redis extra, so a
    backend without it falls back to deleting the keys this phase owns.
    """
    delete_pattern = getattr(cache, "delete_pattern", None)
    if callable(delete_pattern):
        delete_pattern("analytics:*")
        return
    for endpoint, _ in warm_targets():
        cache.delete(analytics_cache_key(endpoint))


base_total = CandidateProfile.objects.count()
base_events = TimelineEvent.objects.count()
seeded_profiles: list[CandidateProfile] = []

print(
    f"\nBaseline: {base_total} candidates, {base_events} timeline events "
    f"(ttl={get_cache_ttl()}s)\n"
)

# Purge before seeding as well as after: a payload cached by an earlier run (or by
# the live dev server) would otherwise be served for the first reads, and every
# "live" assertion below would silently be asserting against stale data. The TTL is
# a backstop, not an invalidation mechanism — nothing purges on a data change.
purge_analytics_cache()

try:
    # --- 1. seed: a big cohort plus a deliberately small one -------------------
    for i in range(6):
        profile = CandidateProfile.objects.create(
            batch=BIG_BATCH,
            hiring_type=DIGITAL,
            region=MAIN_REGION,
            current_status=WAITING,
        )
        seeded_profiles.append(profile)
        # Early offer -> later joining letter, so the offer baseline has samples.
        TimelineEvent.objects.create(
            candidate=profile, event_type="OFFER_LETTER", event_date=date(2026, 1, 1)
        )
        TimelineEvent.objects.create(
            candidate=profile, event_type="JOINING_LETTER", event_date=date(2026, 3, 1 + i)
        )

    for i in range(5):
        profile = CandidateProfile.objects.create(
            batch=BIG_BATCH,
            hiring_type=DIGITAL,
            region=MAIN_REGION,
            current_status=JL_RECEIVED,
        )
        seeded_profiles.append(profile)
        # Survey -> joining letter, so the requirement's literal baseline has samples.
        TimelineEvent.objects.create(
            candidate=profile, event_type="READINESS_SURVEY", event_date=date(2026, 2, 1)
        )
        TimelineEvent.objects.create(
            candidate=profile, event_type="JOINING_LETTER", event_date=date(2026, 3, 10 + i)
        )

    for _ in range(3):
        seeded_profiles.append(
            CandidateProfile.objects.create(
                batch=SMALL_BATCH,
                hiring_type=DIGITAL,
                region=SMALL_REGION,
                current_status=WAITING,
            )
        )

    seeded_ids = {str(p.id) for p in seeded_profiles}
    total_now = CandidateProfile.objects.count()

    # --- 2. anonymous access to all five endpoints ----------------------------
    endpoints = {
        "overview": "/api/v1/analytics/overview/",
        "batches": "/api/v1/analytics/batches/",
        "hiring-types": "/api/v1/analytics/hiring-types/",
        "regions": "/api/v1/analytics/regions/",
        "public-stats": "/api/v1/public/stats/",
    }
    responses = {name: get(path) for name, path in endpoints.items()}
    check(
        "1. all five endpoints answer anonymously with 200",
        all(r.status_code == 200 for r in responses.values()),
        ", ".join(f"{n}={r.status_code}" for n, r in responses.items()),
    )

    overview = responses["overview"].json()
    check(
        "2. overview carries 04 §48's keys plus generated_at",
        {
            "data_source",
            "generated_at",
            "total_candidates",
            "waiting_for_joining_letter",
            "joining_letters_reported",
            "joined_reported",
        }
        <= set(overview)
        and overview["generated_at"].endswith("Z"),
        f"keys={sorted(overview)}",
    )
    check(
        "3. overview total includes the 14 seeded candidates",
        overview["total_candidates"] == total_now,
        f"total={overview['total_candidates']} expected={total_now}",
    )

    wait_times = overview["wait_times"]
    offer = wait_times["offer_to_joining_letter"]
    survey = wait_times["survey_to_joining_letter"]
    check(
        "4. both wait-time baselines ship, each disclosed (D-13/D-16)",
        offer["baseline"] == "OFFER_LETTER"
        and survey["baseline"] == "READINESS_SURVEY"
        and offer["suppressed"] is False
        and survey["suppressed"] is False
        and offer["sample_size"] == sum(offer["baseline_source_counts"].values())
        and survey["baseline_source_counts"]["READINESS_SURVEY_EVENT"] == survey["sample_size"],
        f"offer={offer['sample_size']}d={offer['average_days']} "
        f"survey={survey['sample_size']}d={survey['average_days']}",
    )
    check(
        "5. the two baselines measure different intervals",
        survey["average_days"] < offer["average_days"],
        f"survey={survey['average_days']} < offer={offer['average_days']}",
    )

    check(
        "6. every response is attributed and disclaimed (ANAL-05)",
        all(
            body.get("data_source") == "COMMUNITY_REPORTED" and body.get("disclaimer")
            for body in (r.json() for r in responses.values())
        ),
    )

    # --- 3. the per-row floor over HTTP ---------------------------------------
    batches = responses["batches"].json()
    batch_rows = {row["batch"]: row for row in batches["results"]}
    # Asserted as an invariant rather than "the 2026 row is gone": the dev database
    # already holds 2026 candidates, so which rows exist is not the drill's to
    # predict. No row below the floor may appear anywhere, full stop.
    check(
        "7. per-row floor: no breakdown row below the floor is served (D-01)",
        batches["suppressed"] is False
        and batch_rows
        and all(row["candidate_count"] >= 5 for row in batches["results"]),
        f"rows={sorted(batch_rows)} counts={[r['candidate_count'] for r in batches['results']]}",
    )
    check(
        "8. the surviving rows are the real cohorts",
        batch_rows[BIG_BATCH]["candidate_count"] >= 11,
        f"{BIG_BATCH}={batch_rows[BIG_BATCH]['candidate_count']}",
    )

    regions = responses["regions"].json()
    region_rows = {row["region"] for row in regions["results"]}
    check(
        "9. per-row floor: the 3-candidate region row is absent (D-01)",
        SMALL_REGION not in region_rows and MAIN_REGION in region_rows,
        f"regions={sorted(region_rows)[:4]}",
    )

    # A slice that is guaranteed below the floor: the drill's own unique region, via
    # an endpoint that actually accepts a region filter.
    tiny_slice = get("/api/v1/analytics/batches/", region=SMALL_REGION).json()
    check(
        "10. a below-floor slice returns the 04 §53 payload (D-02)",
        tiny_slice.get("suppressed") is True
        and set(tiny_slice) == {"data_source", "disclaimer", "suppressed", "message"},
        f"keys={sorted(tiny_slice)}",
    )

    # --- 4. filter validation -------------------------------------------------
    bad_stream = get("/api/v1/analytics/batches/", hiring_type="SENIOR")
    bad_batch = get("/api/v1/analytics/hiring-types/", batch="2019")
    bad_region = get("/api/v1/analytics/batches/", region="<script>alert(1)</script>")
    check(
        "11. unknown filters return 400 invalid_filter naming the parameter (D-12)",
        bad_stream.status_code == 400
        and bad_stream.json()["error"] == "invalid_filter"
        and bad_stream.json()["param"] == "hiring_type"
        and bad_batch.status_code == 400
        and bad_region.status_code == 400,
        f"{bad_stream.status_code}/{bad_batch.status_code}/{bad_region.status_code}",
    )

    upper = get("/api/v1/analytics/batches/", region=f"  {MAIN_REGION}  ").json()
    lower = get("/api/v1/analytics/batches/", region=MAIN_REGION.lower()).json()
    check(
        "12. case/whitespace variations share one cache key (D-12)",
        upper == lower and upper["total_in_cohort"] == 11,
        f"total={upper['total_in_cohort']}",
    )

    # --- 5. caching -----------------------------------------------------------
    first = get("/api/v1/analytics/overview/").json()
    extra = CandidateProfile.objects.create(
        batch=BIG_BATCH, hiring_type=DIGITAL, region=MAIN_REGION, current_status=WAITING
    )
    seeded_profiles.append(extra)
    cached_hit = get("/api/v1/analytics/overview/").json()
    check(
        "13. a cache hit serves the stored payload and keeps generated_at (D-04/D-06)",
        cached_hit == first and cached_hit["total_candidates"] == total_now,
        f"cached_total={cached_hit['total_candidates']} live_total={total_now + 1}",
    )

    # `generated_at` has second resolution, so wait out the current second before
    # proving the refresh restamps it; otherwise this compares a timestamp with
    # itself and passes vacuously.
    time.sleep(1.1)
    warmed = warm_analytics_cache()
    after_warm = get("/api/v1/analytics/overview/").json()
    check(
        "14. the warmup refreshes the hot keys and restamps them (D-05/D-07)",
        warmed == len(warm_targets()) == 5
        and after_warm["total_candidates"] == total_now + 1
        and after_warm["generated_at"] > first["generated_at"],
        f"warmed={warmed} total={after_warm['total_candidates']} "
        f"stamp {first['generated_at']} -> {after_warm['generated_at']}",
    )
    check(
        "15. the warmup left a payload in the cache for every endpoint",
        all(cache.get(analytics_cache_key(endpoint)) is not None for endpoint, _ in warm_targets()),
    )

    # --- 6. absent route, no PII ---------------------------------------------
    absent = get("/api/v1/analytics/timeline/")
    check(
        "16. 04 §52 /analytics/timeline/ is absent by decision (D-10)",
        absent.status_code == 404,
        f"status={absent.status_code}",
    )

    bodies = " ".join(r.content.decode() for r in responses.values())
    leaked = [needle for needle in seeded_ids if needle in bodies]
    check(
        "17. no candidate identifier appears in any response",
        not leaked and MAIN_REGION in bodies,
        f"leaked={leaked}",
    )

    stats = responses["public-stats"].json()
    check(
        "18. public stats carries 04 §80's keys, not the overview's (D-09)",
        {"registered_candidates", "community_posts", "timeline_events"} <= set(stats)
        and "total_candidates" not in stats,
        f"candidates={stats['registered_candidates']}",
    )

finally:
    # --- cleanup: remove every row this drill created -------------------------
    TimelineEvent.objects.filter(candidate__in=seeded_profiles).delete()
    CandidateProfile.objects.filter(id__in=[p.id for p in seeded_profiles]).delete()

    # Drop the drill-computed payloads, then re-warm so the cache describes the
    # restored baseline rather than the seeded one.
    purge_analytics_cache()
    warm_analytics_cache()

# --- 7. cleanup verification (always runs, even after a failed check) ---------
restored = CandidateProfile.objects.count() == base_total
events_restored = TimelineEvent.objects.count() == base_events
check(
    "19. cleanup restores the database and the cache to its exact baseline",
    restored
    and events_restored
    and CandidateProfile.objects.filter(region__in=[MAIN_REGION, SMALL_REGION]).count() == 0
    and cache.get(analytics_cache_key("overview"))["total_candidates"] == base_total,
    f"candidates={CandidateProfile.objects.count()}/{base_total} "
    f"events={TimelineEvent.objects.count()}/{base_events}",
)

passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\nDrill finished: {passed}/{total} passed.")
if passed != total:
    sys.exit(1)
