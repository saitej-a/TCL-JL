"""Stage 2 live drill for Phase 7.1 (run inside the web container).

7.1 is service-only (no HTTP surface, no models), so unlike 5.2's REST drill this
one is ORM against the real dev database: it seeds a synthetic cohort across
batches, hiring streams and regions, then proves the service layer end-to-end at
the layer that holds the logic, and cleans every row up after itself. Every check
prints PASS/FAIL and the script exits non-zero on any failure.

What it proves:
1. Cohort aggregation over batches, hiring streams and regions (ANAL-01/02 seam).
2. Wait-time metrics with the full D1 fallback hierarchy — OFFER_LETTER event ->
   INTERVIEW event -> CandidateProfile.offer_letter_date -> interview_date — plus
   exclusion of negative intervals (ANAL-03).
3. Mandatory <5 cohort privacy suppression on every scoped slice (ANAL-04).
4. Mandatory COMMUNITY_REPORTED attribution + disclosure on every payload (D4).
5. Cleanup returns the database to its exact baseline counts.

Usage: docker compose run --rm --no-deps web python .planning/phases/<this>/drill_07_01.py
"""

from __future__ import annotations

import os
import sys
import uuid as uuidlib
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath("."))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from apps.analytics.services import (
    DATA_SOURCE_LABEL,
    DISCLAIMER_TEXT,
    RECEIVED_JL_STATUSES,
    SUPPRESSED_MESSAGE,
    WAITING_STATUSES,
    calculate_wait_time_metrics,
    check_privacy_suppression,
    get_batch_breakdown,
    get_community_overview_stats,
    get_hiring_type_breakdown,
    get_region_breakdown,
)
from apps.candidates.models import CandidateProfile
from apps.timeline.models import TimelineEvent

STAMP = uuidlib.uuid4().hex[:8]
MAIN_REGION = f"DRILL-7-1-MAIN-{STAMP}"
SMALL_REGION = f"DRILL-7-1-SMALL-{STAMP}"
BASE_DAY = date(2026, 1, 1)

PRIME = CandidateProfile.HiringType.PRIME
DIGITAL = CandidateProfile.HiringType.DIGITAL
NINJA = CandidateProfile.HiringType.NINJA
WAITING = CandidateProfile.Status.WAITING_FOR_JOINING_LETTER
REGISTERED = CandidateProfile.Status.REGISTERED
JL_RECEIVED = CandidateProfile.Status.JOINING_LETTER_RECEIVED
JOINED = CandidateProfile.Status.JOINED
WITHDRAWN = CandidateProfile.Status.WITHDRAWN

results: list[tuple[str, bool, str]] = []
seeded_profiles: list[CandidateProfile] = []
seeded_events: list[TimelineEvent] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))


def seed(batch: str, hiring_type: str, region: str, status: str, **dates) -> CandidateProfile:
    profile = CandidateProfile.objects.create(
        batch=batch,
        hiring_type=hiring_type,
        region=region,
        current_status=status,
        **dates,
    )
    seeded_profiles.append(profile)
    return profile


def event(profile: CandidateProfile, event_type: str, day_offset: int) -> TimelineEvent:
    row = TimelineEvent.objects.create(
        candidate=profile,
        event_type=event_type,
        event_date=BASE_DAY + timedelta(days=day_offset),
    )
    seeded_events.append(row)
    return row


# --- baseline: the drill must be safe on a populated dev database -------------
base_total = CandidateProfile.objects.count()
base_waiting = CandidateProfile.objects.filter(current_status__in=WAITING_STATUSES).count()
base_jl = CandidateProfile.objects.filter(current_status__in=RECEIVED_JL_STATUSES).count()
base_joined = CandidateProfile.objects.filter(current_status=JOINED).count()
base_events = TimelineEvent.objects.count()

print(
    f"Baseline: candidates={base_total} waiting={base_waiting} jl={base_jl} "
    f"joined={base_joined} events={base_events}"
)

try:
    # --- seed the MAIN cohort (7 profiles, 6 with a calculable wait time) ------
    # p1, p2 — OFFER_LETTER event -> JOINING_LETTER (10 days), batch 2024 / PRIME.
    for _ in range(2):
        p = seed("2024", PRIME, MAIN_REGION, WAITING)
        event(p, TimelineEvent.EventType.OFFER_LETTER, 0)
        event(p, TimelineEvent.EventType.JOINING_LETTER, 10)

    # p3, p4 — D1 fallback 1: no offer event, INTERVIEW event -> JL (20 days).
    p3 = seed("2024", DIGITAL, MAIN_REGION, REGISTERED)
    event(p3, TimelineEvent.EventType.INTERVIEW, 0)
    event(p3, TimelineEvent.EventType.JOINING_LETTER, 20)
    p4 = seed("2025", DIGITAL, MAIN_REGION, REGISTERED)
    event(p4, TimelineEvent.EventType.INTERVIEW, 0)
    event(p4, TimelineEvent.EventType.JOINING_LETTER, 20)

    # p5 — D1 fallback 2: no baseline event, profile.offer_letter_date -> JL (30 days).
    p5 = seed("2025", PRIME, MAIN_REGION, JL_RECEIVED, offer_letter_date=BASE_DAY)
    event(p5, TimelineEvent.EventType.JOINING_LETTER, 30)

    # p6 — D1 fallback 3: profile.interview_date -> JL (40 days).
    p6 = seed("2025", DIGITAL, MAIN_REGION, JOINED, interview_date=BASE_DAY)
    event(p6, TimelineEvent.EventType.JOINING_LETTER, 40)

    # p7 — anomalous: JL dated before its offer letter; must never enter the sample.
    p7 = seed("2025", NINJA, MAIN_REGION, WITHDRAWN)
    event(p7, TimelineEvent.EventType.OFFER_LETTER, 50)
    event(p7, TimelineEvent.EventType.JOINING_LETTER, 0)

    # --- seed the SMALL cohort (2 profiles, deliberately below the floor) -----
    for _ in range(2):
        p = seed("2026", PRIME, SMALL_REGION, WAITING)
        event(p, TimelineEvent.EventType.OFFER_LETTER, 0)
        event(p, TimelineEvent.EventType.JOINING_LETTER, 15)

    main_cohort = CandidateProfile.objects.filter(region=MAIN_REGION)
    small_cohort = CandidateProfile.objects.filter(region=SMALL_REGION)

    # --- 1. overview aggregation ----------------------------------------------
    overview = get_community_overview_stats()
    check(
        "1. overview is not suppressed and is attributed",
        overview.get("suppressed") is False
        and overview.get("data_source") == DATA_SOURCE_LABEL
        and overview.get("disclaimer") == DISCLAIMER_TEXT,
        f"keys={sorted(overview)}",
    )
    check(
        "2. overview total reflects the 9 seeded candidates",
        overview.get("total_candidates") == base_total + 9,
        f"got={overview.get('total_candidates')} expected={base_total + 9}",
    )
    check(
        "3. overview waiting count reflects the 6 seeded waiting candidates",
        overview.get("waiting_for_joining_letter") == base_waiting + 6,
        f"got={overview.get('waiting_for_joining_letter')} expected={base_waiting + 6}",
    )
    check(
        "4. overview JL/joined counts reflect the seeded joiners",
        overview.get("joining_letters_reported") == base_jl + 2
        and overview.get("joined_reported") == base_joined + 1,
        f"jl={overview.get('joining_letters_reported')} joined={overview.get('joined_reported')}",
    )

    # --- 2. batch breakdown ---------------------------------------------------
    batch_payload = get_batch_breakdown(region=MAIN_REGION)
    batch_rows = {
        str(row["batch"]): row for row in batch_payload.get("results", []) if "batch" in row
    }
    check(
        "5. batch breakdown scopes to the seeded cohort (7) unsuppressed",
        batch_payload.get("suppressed") is False
        and batch_payload.get("total_in_cohort") == 7
        and set(batch_rows) == {"2024", "2025"},
        f"total={batch_payload.get('total_in_cohort')} batches={sorted(batch_rows)}",
    )
    check(
        "6. batch 2024 row: 3 candidates, 3 waiting, 0 JL reported",
        batch_rows.get("2024", {}).get("candidate_count") == 3
        and batch_rows.get("2024", {}).get("waiting_for_joining_letter") == 3
        and batch_rows.get("2024", {}).get("joining_letter_reported") == 0,
        f"row={batch_rows.get('2024')}",
    )
    check(
        "7. batch 2025 row: 4 candidates, 1 waiting, 2 JL reported",
        batch_rows.get("2025", {}).get("candidate_count") == 4
        and batch_rows.get("2025", {}).get("waiting_for_joining_letter") == 1
        and batch_rows.get("2025", {}).get("joining_letter_reported") == 2,
        f"row={batch_rows.get('2025')}",
    )

    # --- 3. hiring-stream breakdown -------------------------------------------
    stream_payload = get_hiring_type_breakdown(region=MAIN_REGION)
    stream_rows = {
        row["hiring_type"]: row["candidate_count"] for row in stream_payload.get("results", [])
    }
    check(
        "8. hiring-type breakdown splits the cohort by stream (PRIME 3 / DIGITAL 3 / NINJA 1)",
        stream_payload.get("suppressed") is False
        and stream_payload.get("total_in_cohort") == 7
        and stream_rows == {PRIME: 3, DIGITAL: 3, NINJA: 1},
        f"streams={stream_rows}",
    )

    # --- 4. regional breakdown ------------------------------------------------
    region_payload = get_region_breakdown()
    region_rows = {
        row["region"]: row["candidate_count"] for row in region_payload.get("results", [])
    }
    check(
        "9. regional breakdown surfaces the seeded region as its own row (7)",
        region_payload.get("suppressed") is False and region_rows.get(MAIN_REGION) == 7,
        f"row={region_rows.get(MAIN_REGION)}",
    )

    # --- 5. mandatory <5 privacy suppression ----------------------------------
    small_batch = get_batch_breakdown(region=SMALL_REGION)
    small_stream = get_hiring_type_breakdown(region=SMALL_REGION)
    check(
        "10. batch + stream breakdowns fully suppress the 2-candidate cohort",
        small_batch.get("suppressed") is True
        and small_batch.get("message") == SUPPRESSED_MESSAGE
        and small_stream.get("suppressed") is True
        and "results" not in small_batch
        and "results" not in small_stream
        and "total_in_cohort" not in small_batch,
        f"batch={sorted(small_batch)} stream={sorted(small_stream)}",
    )
    check(
        "11. suppressed payloads still carry attribution, never numbers",
        small_batch.get("data_source") == DATA_SOURCE_LABEL
        and small_batch.get("disclaimer") == DISCLAIMER_TEXT
        and all(
            key not in small_batch
            for key in ("total_candidates", "total_in_cohort", "candidate_count", "results")
        ),
        f"keys={sorted(small_batch)}",
    )
    suppressed_flag, suppressed_payload = check_privacy_suppression(4)
    allowed_flag, allowed_payload = check_privacy_suppression(5)
    check(
        "12. threshold is exactly 5 (4 suppressed, 5 allowed)",
        suppressed_flag is True
        and suppressed_payload is not None
        and suppressed_payload["message"] == SUPPRESSED_MESSAGE
        and allowed_flag is False
        and allowed_payload is None,
    )

    # --- 6. wait-time metrics with the D1 fallback hierarchy ------------------
    wait = calculate_wait_time_metrics(queryset=main_cohort)
    check(
        "13. wait-time cohort of 6 reports mean/median/min/max with attribution",
        wait.get("suppressed") is False
        and wait.get("data_source") == DATA_SOURCE_LABEL
        and wait.get("disclaimer") == DISCLAIMER_TEXT
        and wait.get("sample_size") == 6,
        f"payload={wait}",
    )
    check(
        "14. fallback hierarchy yields the expected wait-time statistics",
        wait.get("average_days") == 21.7
        and wait.get("median_days") == 20.0
        and wait.get("min_days") == 10
        and wait.get("max_days") == 40,
        f"avg={wait.get('average_days')} med={wait.get('median_days')} "
        f"min={wait.get('min_days')} max={wait.get('max_days')}",
    )
    small_wait = calculate_wait_time_metrics(queryset=small_cohort)
    check(
        "15. wait-time sample below the floor is suppressed with no statistics",
        small_wait.get("suppressed") is True
        and small_wait.get("message") == SUPPRESSED_MESSAGE
        and "average_days" not in small_wait
        and "sample_size" not in small_wait,
        f"keys={sorted(small_wait)}",
    )

finally:
    # --- cleanup: remove every row this drill created -------------------------
    TimelineEvent.objects.filter(candidate__in=seeded_profiles).delete()
    CandidateProfile.objects.filter(id__in=[p.id for p in seeded_profiles]).delete()

# --- 7. cleanup verification (always runs, even after a failed check) ---------
check(
    "16. cleanup removes every seeded candidate and timeline event",
    CandidateProfile.objects.count() == base_total
    and TimelineEvent.objects.count() == base_events
    and CandidateProfile.objects.filter(region__in=[MAIN_REGION, SMALL_REGION]).count() == 0,
    f"candidates={CandidateProfile.objects.count()}/{base_total} "
    f"events={TimelineEvent.objects.count()}/{base_events}",
)

passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\nDrill finished: {passed}/{total} passed.")
if passed != total:
    sys.exit(1)
