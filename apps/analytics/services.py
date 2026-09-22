"""Core analytics and cohort aggregation service layer (Phase 7.1).

Enforces:
- ANAL-04: Mandatory <5 privacy suppression threshold (ANALYTICS_MIN_COHORT_SIZE).
- ANAL-03: Average and distribution wait-time calculations with fallback hierarchy.
- D3 / AI Agent Directive 7.5: Read-only data aggregation; zero write models.
- D4 / AI Agent Directive 7.2: Attributed data source and non-affiliation disclaimer on all outputs.
"""

from __future__ import annotations

import logging
from datetime import date
from statistics import median
from typing import Any

from django.conf import settings
from django.db.models import Count, QuerySet

from apps.candidates.models import CandidateProfile
from apps.timeline.models import TimelineEvent

logger = logging.getLogger("analytics")

DATA_SOURCE_LABEL = "COMMUNITY_REPORTED"
DISCLAIMER_TEXT = (
    "These figures are based on community-submitted data and are not official TCS statistics."
)
SUPPRESSED_MESSAGE = "Not enough community data to display this breakdown."

# Waiting statuses matching Phase 4.2 dashboard contract
WAITING_STATUSES = {
    CandidateProfile.Status.REGISTERED,
    CandidateProfile.Status.INTERVIEWED,
    CandidateProfile.Status.SELECTED,
    CandidateProfile.Status.OFFER_RECEIVED,
    CandidateProfile.Status.READINESS_SURVEY,
    CandidateProfile.Status.WAITING_FOR_JOINING_LETTER,
}

RECEIVED_JL_STATUSES = {
    CandidateProfile.Status.JOINING_LETTER_RECEIVED,
    CandidateProfile.Status.JOINING_DATE_RECEIVED,
    CandidateProfile.Status.JOINED,
}


def get_min_cohort_size() -> int:
    """Return the configured minimum cohort size for privacy suppression."""
    return getattr(settings, "ANALYTICS_MIN_COHORT_SIZE", 5)


def check_privacy_suppression(count: int) -> tuple[bool, dict[str, Any] | None]:
    """Check whether a cohort count triggers the mandatory privacy suppression threshold.

    Returns:
        (is_suppressed, suppression_payload_or_None)
    """
    threshold = get_min_cohort_size()
    if count < threshold:
        return True, {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "suppressed": True,
            "message": SUPPRESSED_MESSAGE,
        }
    return False, None


def get_community_overview_stats() -> dict[str, Any]:
    """Aggregate high-level community recruitment benchmarks.

    Returns overview counts of candidates tracked, waiting, received JL, and joined.
    Applies global privacy suppression if total tracked candidates < threshold.
    """
    total = CandidateProfile.objects.count()
    is_suppressed, suppression_payload = check_privacy_suppression(total)
    if is_suppressed and suppression_payload:
        return suppression_payload

    counts = {
        row["current_status"]: row["n"]
        for row in CandidateProfile.objects.values("current_status").annotate(n=Count("id"))
    }

    waiting_count = sum(counts.get(s, 0) for s in WAITING_STATUSES)
    received_jl_count = sum(counts.get(s, 0) for s in RECEIVED_JL_STATUSES)
    joined_count = counts.get(CandidateProfile.Status.JOINED, 0)

    return {
        "data_source": DATA_SOURCE_LABEL,
        "disclaimer": DISCLAIMER_TEXT,
        "suppressed": False,
        "total_candidates": total,
        "waiting_for_joining_letter": waiting_count,
        "joining_letters_reported": received_jl_count,
        "joined_reported": joined_count,
    }


def get_batch_breakdown(
    hiring_type: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Calculate aggregate benchmarks grouped by candidate batch year.

    Supports filtering by hiring_type and region. If the total filtered cohort
    is below the privacy threshold, returns a suppressed response with zero data.
    """
    qs = CandidateProfile.objects.all()
    if hiring_type:
        qs = qs.filter(hiring_type=hiring_type)
    if region:
        qs = qs.filter(region__iexact=region)

    total = qs.count()
    is_suppressed, suppression_payload = check_privacy_suppression(total)
    if is_suppressed and suppression_payload:
        return suppression_payload

    batches_data = []
    # Query distinct batches present
    batch_rows = qs.values("batch").annotate(total_in_batch=Count("id")).order_by("batch")

    for b in batch_rows:
        batch_val = b["batch"]
        batch_qs = qs.filter(batch=batch_val)
        b_counts = {
            row["current_status"]: row["n"]
            for row in batch_qs.values("current_status").annotate(n=Count("id"))
        }
        waiting = sum(b_counts.get(s, 0) for s in WAITING_STATUSES)
        jl_reported = sum(b_counts.get(s, 0) for s in RECEIVED_JL_STATUSES)

        batches_data.append(
            {
                "batch": batch_val,
                "candidate_count": b["total_in_batch"],
                "waiting_for_joining_letter": waiting,
                "joining_letter_reported": jl_reported,
            }
        )

    return {
        "data_source": DATA_SOURCE_LABEL,
        "disclaimer": DISCLAIMER_TEXT,
        "suppressed": False,
        "total_in_cohort": total,
        "results": batches_data,
    }


def get_hiring_type_breakdown(
    batch: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Calculate aggregate benchmarks grouped by hiring stream (Prime, Digital, Ninja, Other).

    Supports filtering by batch and region. If total filtered cohort < threshold,
    suppresses the entire breakdown.
    """
    qs = CandidateProfile.objects.all()
    if batch:
        qs = qs.filter(batch=batch)
    if region:
        qs = qs.filter(region__iexact=region)

    total = qs.count()
    is_suppressed, suppression_payload = check_privacy_suppression(total)
    if is_suppressed and suppression_payload:
        return suppression_payload

    results = []
    stream_rows = (
        qs.values("hiring_type").annotate(stream_count=Count("id")).order_by("hiring_type")
    )

    for row in stream_rows:
        ht = row["hiring_type"]
        ht_qs = qs.filter(hiring_type=ht)
        ht_counts = {
            r["current_status"]: r["n"]
            for r in ht_qs.values("current_status").annotate(n=Count("id"))
        }
        waiting = sum(ht_counts.get(s, 0) for s in WAITING_STATUSES)
        jl_reported = sum(ht_counts.get(s, 0) for s in RECEIVED_JL_STATUSES)

        results.append(
            {
                "hiring_type": ht,
                "candidate_count": row["stream_count"],
                "waiting_for_joining_letter": waiting,
                "joining_letter_reported": jl_reported,
            }
        )

    return {
        "data_source": DATA_SOURCE_LABEL,
        "disclaimer": DISCLAIMER_TEXT,
        "suppressed": False,
        "total_in_cohort": total,
        "results": results,
    }


def get_region_breakdown(
    batch: str | None = None,
    hiring_type: str | None = None,
) -> dict[str, Any]:
    """Calculate aggregate benchmarks grouped by region.

    Enforces cohort threshold: if total candidates in filtered slice < threshold,
    suppresses the breakdown to prevent micro-cohort re-identification.
    """
    qs = CandidateProfile.objects.all()
    if batch:
        qs = qs.filter(batch=batch)
    if hiring_type:
        qs = qs.filter(hiring_type=hiring_type)

    total = qs.count()
    is_suppressed, suppression_payload = check_privacy_suppression(total)
    if is_suppressed and suppression_payload:
        return suppression_payload

    results = []
    region_rows = qs.values("region").annotate(region_count=Count("id")).order_by("-region_count")

    for row in region_rows:
        reg = row["region"]
        reg_qs = qs.filter(region=reg)
        reg_counts = {
            r["current_status"]: r["n"]
            for r in reg_qs.values("current_status").annotate(n=Count("id"))
        }
        waiting = sum(reg_counts.get(s, 0) for s in WAITING_STATUSES)
        jl_reported = sum(reg_counts.get(s, 0) for s in RECEIVED_JL_STATUSES)

        results.append(
            {
                "region": reg,
                "candidate_count": row["region_count"],
                "waiting_for_joining_letter": waiting,
                "joining_letter_reported": jl_reported,
            }
        )

    return {
        "data_source": DATA_SOURCE_LABEL,
        "disclaimer": DISCLAIMER_TEXT,
        "suppressed": False,
        "total_in_cohort": total,
        "results": results,
    }


def calculate_wait_time_metrics(
    queryset: QuerySet[CandidateProfile] | None = None,
) -> dict[str, Any]:
    """Calculate wait-time statistics to JOINING_LETTER (ANAL-03, D1).

    Priority for start baseline:
    1. TimelineEvent(event_type=OFFER_LETTER)
    2. Fallback: TimelineEvent(event_type=INTERVIEW)
    3. Fallback: CandidateProfile.offer_letter_date
    4. Fallback: CandidateProfile.interview_date

    End milestone:
    TimelineEvent(event_type=JOINING_LETTER)

    Returns:
        average_days, median_days, min_days, max_days, sample_size.
        If valid sample_size < ANALYTICS_MIN_COHORT_SIZE, returns suppressed payload.
    """
    profiles = queryset if queryset is not None else CandidateProfile.objects.all()

    # Pre-filter candidates who have at least one JOINING_LETTER event
    jl_events = TimelineEvent.objects.filter(
        candidate__in=profiles,
        event_type=TimelineEvent.EventType.JOINING_LETTER,
    ).values("candidate_id", "event_date")

    # Earliest JL date per candidate
    jl_date_map: dict[Any, date] = {}
    for ev in jl_events:
        cid = ev["candidate_id"]
        edate = ev["event_date"]
        if cid not in jl_date_map or edate < jl_date_map[cid]:
            jl_date_map[cid] = edate

    if not jl_date_map:
        return {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "suppressed": True,
            "message": SUPPRESSED_MESSAGE,
        }

    relevant_candidate_ids = list(jl_date_map.keys())

    # Fetch relevant baseline events for these candidates
    baseline_events = TimelineEvent.objects.filter(
        candidate_id__in=relevant_candidate_ids,
        event_type__in=[
            TimelineEvent.EventType.OFFER_LETTER,
            TimelineEvent.EventType.INTERVIEW,
        ],
    ).values("candidate_id", "event_type", "event_date")

    offer_event_map: dict[Any, date] = {}
    interview_event_map: dict[Any, date] = {}
    for ev in baseline_events:
        cid = ev["candidate_id"]
        etype = ev["event_type"]
        edate = ev["event_date"]
        if etype == TimelineEvent.EventType.OFFER_LETTER:
            if cid not in offer_event_map or edate < offer_event_map[cid]:
                offer_event_map[cid] = edate
        elif etype == TimelineEvent.EventType.INTERVIEW:
            if cid not in interview_event_map or edate < interview_event_map[cid]:
                interview_event_map[cid] = edate

    # Fetch candidate profile dates for fallbacks
    profile_date_rows = CandidateProfile.objects.filter(id__in=relevant_candidate_ids).values(
        "id", "offer_letter_date", "interview_date"
    )
    profile_dates = {row["id"]: row for row in profile_date_rows}

    wait_days_list: list[int] = []

    for cid, jl_date in jl_date_map.items():
        start_date: date | None = None

        # Priority 1: TimelineEvent OFFER_LETTER
        if cid in offer_event_map:
            start_date = offer_event_map[cid]
        # Priority 2: TimelineEvent INTERVIEW
        elif cid in interview_event_map:
            start_date = interview_event_map[cid]
        # Priority 3: CandidateProfile offer_letter_date
        elif cid in profile_dates and profile_dates[cid]["offer_letter_date"]:
            start_date = profile_dates[cid]["offer_letter_date"]
        # Priority 4: CandidateProfile interview_date
        elif cid in profile_dates and profile_dates[cid]["interview_date"]:
            start_date = profile_dates[cid]["interview_date"]

        if start_date is not None and jl_date >= start_date:
            days = (jl_date - start_date).days
            wait_days_list.append(days)

    sample_size = len(wait_days_list)
    is_suppressed, suppression_payload = check_privacy_suppression(sample_size)
    if is_suppressed and suppression_payload:
        return suppression_payload

    avg_val = round(sum(wait_days_list) / sample_size, 1)
    med_val = round(float(median(wait_days_list)), 1)
    min_val = min(wait_days_list)
    max_val = max(wait_days_list)

    return {
        "data_source": DATA_SOURCE_LABEL,
        "disclaimer": DISCLAIMER_TEXT,
        "suppressed": False,
        "sample_size": sample_size,
        "average_days": avg_val,
        "median_days": med_val,
        "min_days": min_val,
        "max_days": max_val,
    }
