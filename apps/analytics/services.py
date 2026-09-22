"""Core analytics and cohort aggregation service layer (Phase 7.1; exposed in 7.2).

Enforces:
- ANAL-04: Mandatory <5 privacy suppression threshold (ANALYTICS_MIN_COHORT_SIZE),
  applied to the filtered slice **and** to every result row (7.2 D-01/D-02/D-03).
- ANAL-03: Average and distribution wait-time calculations, published on both
  baselines (7.2 D-13) — READINESS_SURVEY -> JOINING_LETTER (the requirement's
  literal "survey submission") and OFFER_LETTER -> JOINING_LETTER (7.1 D1's chain,
  with its four-step fallback).
- ANAL-05: COMMUNITY_REPORTED attribution, the non-affiliation disclaimer and a
  compute-time `generated_at` on every non-suppressed payload (7.2 D-06).
- 7.2 D-12: whitelist filter validation via `InvalidAnalyticsFilter`.
- D3 / AI Agent Directive 7.5: Read-only data aggregation; zero write models.
- 7.2 D-04: this module deliberately imports no cache module — computation stays
  pure and caching lives at the edge (`apps/analytics/cache.py`).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
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

# Baseline labels published with each wait-time metric (7.2 D-16).
BASELINE_OFFER_LETTER = "OFFER_LETTER"
BASELINE_READINESS_SURVEY = "READINESS_SURVEY"

# Chain-step labels for the offer->JL metric (7.2 D-16): which of 7.1 D1's four
# sources resolved each sample, so a fallback-heavy sample is visibly weaker
# evidence than an event-sourced one.
SOURCE_OFFER_LETTER_EVENT = "OFFER_LETTER_EVENT"
SOURCE_INTERVIEW_EVENT = "INTERVIEW_EVENT"
SOURCE_PROFILE_OFFER_DATE = "PROFILE_OFFER_LETTER_DATE"
SOURCE_PROFILE_INTERVIEW_DATE = "PROFILE_INTERVIEW_DATE"
SOURCE_READINESS_SURVEY_EVENT = "READINESS_SURVEY_EVENT"

# Wait-time baselines exposed through the overview payload (7.2 D-14).
WAIT_TIME_METRIC_OFFER = "offer_to_joining_letter"
WAIT_TIME_METRIC_SURVEY = "survey_to_joining_letter"

# Bound for the free-text region filter (7.2 D-12): the model's own max_length.
REGION_FILTER_MAX_LENGTH = 100

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


class InvalidAnalyticsFilter(ValueError):
    """An unknown ``?filter=`` value (7.2 D-12).

    Raised in the service layer and translated into HTTP 400 by the view, so the
    validation rule has exactly one home (thin views over services, 5.2/6.2).
    """

    def __init__(self, param: str, value: Any, allowed: list[str] | None = None) -> None:
        self.param = param
        self.value = value
        self.allowed = allowed or []
        detail = f"Unknown {param}={value!r}"
        if self.allowed:
            detail += f"; expected one of {', '.join(self.allowed)}"
        super().__init__(detail)


def get_min_cohort_size() -> int:
    """Return the configured minimum cohort size for privacy suppression."""
    return getattr(settings, "ANALYTICS_MIN_COHORT_SIZE", 5)


def suppression_payload() -> dict[str, Any]:
    """The 04 §53 suppression shape, and only that shape.

    Deliberately carries no `generated_at` (7.2 D-06): the suppressed payload's
    four-key contract is asserted by tests and by the live drill, and a timestamp
    on a payload with no data answers a question nobody asked.
    """
    return {
        "data_source": DATA_SOURCE_LABEL,
        "disclaimer": DISCLAIMER_TEXT,
        "suppressed": True,
        "message": SUPPRESSED_MESSAGE,
    }


def _generated_at() -> str:
    """UTC ISO-8601 with a `Z` suffix, microseconds stripped (04 §48's shape)."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _with_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Stamp a **non-suppressed** payload with its compute time (7.2 D-06).

    Because the stamp is written before the payload is cached, a cache hit keeps
    reporting when its numbers were computed rather than when it was served.
    """
    payload["generated_at"] = _generated_at()
    return payload


def check_privacy_suppression(count: int) -> tuple[bool, dict[str, Any] | None]:
    """Check whether a cohort count triggers the mandatory privacy suppression threshold.

    Returns:
        (is_suppressed, suppression_payload_or_None)
    """
    if count < get_min_cohort_size():
        return True, suppression_payload()
    return False, None


def apply_row_floor(
    rows: list[dict[str, Any]],
    count_key: str = "candidate_count",
) -> list[dict[str, Any]] | None:
    """Apply the `<5` floor to each result row (7.2 D-01/D-03).

    A below-floor row is dropped **entirely** — never zeroed, never labeled, never
    counted — because a zeroed bucket still discloses that the bucket exists and a
    withheld-count field discloses exactly where the small cohorts are.

    Returns:
        The surviving rows, or ``None`` when nothing clears the floor (the caller
        then returns the 04 §53 payload, per D-02).
    """
    floor = get_min_cohort_size()
    surviving = [row for row in rows if row.get(count_key, 0) >= floor]
    return surviving or None


def validate_filters(
    hiring_type: str | None = None,
    region: str | None = None,
    batch: str | None = None,
) -> dict[str, str]:
    """Whitelist-validate and normalize the public filter parameters (7.2 D-12).

    Normalization matters for more than tidiness: `?region=Goa` and `?region=goa`
    must share one cache key, or an anonymous caller can mint unbounded cache
    entries with case variations alone.

    Region is deliberately **not** validated against a vocabulary — 3.1 D3 makes it
    a free-text field ("candidates in any location are supported"), and a whitelist
    built from regions that currently have candidates would 400 the legitimate
    case of a real region with no data yet. It is bounded by length and charset
    instead, which bounds the key space alongside the round-tripping normalization.
    The charset is deliberately permissive enough for real place names (`Sector 62`,
    `Navi Mumbai`, `St. Mary's`) — safety comes from the digest (see below), so this
    is input hygiene rather than an injection barrier.

    Raises:
        InvalidAnalyticsFilter: for an unknown hiring stream or batch year, or a
        region that cannot be a real one.
    """
    normalized: dict[str, str] = {}

    if hiring_type:
        allowed = list(CandidateProfile.HiringType.values)
        value = hiring_type.strip().upper()
        if value not in allowed:
            raise InvalidAnalyticsFilter("hiring_type", hiring_type, allowed)
        normalized["hiring_type"] = value

    if batch:
        allowed = [str(year) for year in settings.BATCH_YEARS]
        value = batch.strip()
        if value not in allowed:
            raise InvalidAnalyticsFilter("batch", batch, allowed)
        normalized["batch"] = value

    if region:
        value = " ".join(region.split())
        if (
            not value
            or len(value) > REGION_FILTER_MAX_LENGTH
            or not all(ch.isalnum() or ch in " -.'(),/&" for ch in value)
        ):
            raise InvalidAnalyticsFilter("region", region)
        normalized["region"] = value.lower()

    return normalized


def get_community_overview_stats() -> dict[str, Any]:
    """Aggregate high-level community recruitment benchmarks.

    Returns overview counts of candidates tracked, waiting, received JL, and joined,
    plus both wait-time metrics (7.2 D-13/D-14). Applies global privacy suppression
    if total tracked candidates < threshold.
    """
    total = CandidateProfile.objects.count()
    is_suppressed, payload = check_privacy_suppression(total)
    if is_suppressed and payload:
        return payload

    counts = {
        row["current_status"]: row["n"]
        for row in CandidateProfile.objects.values("current_status").annotate(n=Count("id"))
    }

    waiting_count = sum(counts.get(s, 0) for s in WAITING_STATUSES)
    received_jl_count = sum(counts.get(s, 0) for s in RECEIVED_JL_STATUSES)
    joined_count = counts.get(CandidateProfile.Status.JOINED, 0)

    return _with_metadata(
        {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "suppressed": False,
            "total_candidates": total,
            "waiting_for_joining_letter": waiting_count,
            "joining_letters_reported": received_jl_count,
            "joined_reported": joined_count,
            # 7.2 D-14: 04 §47-§53 define no wait-time endpoint, and the dashboard
            # already reads community benchmarks from here, so both baselines ride
            # the cached overview payload rather than inventing a new route.
            "wait_times": {
                WAIT_TIME_METRIC_OFFER: calculate_wait_time_metrics(),
                WAIT_TIME_METRIC_SURVEY: calculate_survey_wait_time_metrics(),
            },
        }
    )


def get_batch_breakdown(
    hiring_type: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Calculate aggregate benchmarks grouped by candidate batch year.

    Supports filtering by hiring_type and region. If the total filtered cohort is
    below the privacy threshold, returns a suppressed response with zero data; if
    the slice clears the floor but individual batch rows do not, those rows are
    dropped (7.2 D-01) and an all-dropped result is suppressed wholesale (D-02).
    """
    qs = CandidateProfile.objects.all()
    if hiring_type:
        qs = qs.filter(hiring_type=hiring_type)
    if region:
        qs = qs.filter(region__iexact=region)

    total = qs.count()
    is_suppressed, payload = check_privacy_suppression(total)
    if is_suppressed and payload:
        return payload

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

    results = apply_row_floor(batches_data)
    if results is None:
        return suppression_payload()

    return _with_metadata(
        {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "suppressed": False,
            "total_in_cohort": total,
            "results": results,
        }
    )


def get_hiring_type_breakdown(
    batch: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Calculate aggregate benchmarks grouped by hiring stream (Prime, Digital, Ninja, Other).

    Supports filtering by batch and region. If total filtered cohort < threshold,
    suppresses the entire breakdown; below-floor stream rows are dropped (7.2 D-01).
    """
    qs = CandidateProfile.objects.all()
    if batch:
        qs = qs.filter(batch=batch)
    if region:
        qs = qs.filter(region__iexact=region)

    total = qs.count()
    is_suppressed, payload = check_privacy_suppression(total)
    if is_suppressed and payload:
        return payload

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

    floored = apply_row_floor(results)
    if floored is None:
        return suppression_payload()

    return _with_metadata(
        {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "suppressed": False,
            "total_in_cohort": total,
            "results": floored,
        }
    )


def get_region_breakdown(
    batch: str | None = None,
    hiring_type: str | None = None,
) -> dict[str, Any]:
    """Calculate aggregate benchmarks grouped by region.

    Enforces cohort threshold: if total candidates in filtered slice < threshold,
    suppresses the breakdown to prevent micro-cohort re-identification. Below-floor
    region rows are dropped too (7.2 D-01) — the strongest case for the per-row
    rule, since a region with 3 candidates is the most identifying row 04 §51 warns
    about ("Do not expose combinations that could identify a single candidate").
    """
    qs = CandidateProfile.objects.all()
    if batch:
        qs = qs.filter(batch=batch)
    if hiring_type:
        qs = qs.filter(hiring_type=hiring_type)

    total = qs.count()
    is_suppressed, payload = check_privacy_suppression(total)
    if is_suppressed and payload:
        return payload

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

    floored = apply_row_floor(results)
    if floored is None:
        return suppression_payload()

    return _with_metadata(
        {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "suppressed": False,
            "total_in_cohort": total,
            "results": floored,
        }
    )


def _earliest_by_candidate(
    queryset: QuerySet[CandidateProfile],
    event_types: list[str],
) -> dict[Any, date]:
    """Map candidate id -> earliest event_date for any of `event_types`."""
    rows = TimelineEvent.objects.filter(
        candidate__in=queryset,
        event_type__in=event_types,
    ).values("candidate_id", "event_date")

    earliest: dict[Any, date] = {}
    for row in rows:
        cid = row["candidate_id"]
        edate = row["event_date"]
        if cid not in earliest or edate < earliest[cid]:
            earliest[cid] = edate
    return earliest


def _wait_time_payload(
    wait_days: list[int],
    baseline: str,
    source_counts: dict[str, int],
) -> dict[str, Any]:
    """Assemble one wait-time metric, gated by its own `<5` sample floor (7.2 D-13).

    Disclosure (7.2 D-16): the metric names its baseline and reports how many
    samples each source contributed, so a fallback-heavy or mixed sample is visible
    rather than being averaged into one confident-looking number.
    """
    sample_size = len(wait_days)
    is_suppressed, payload = check_privacy_suppression(sample_size)
    if is_suppressed and payload:
        return payload

    return _with_metadata(
        {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "suppressed": False,
            "baseline": baseline,
            "baseline_source_counts": source_counts,
            "sample_size": sample_size,
            "average_days": round(sum(wait_days) / sample_size, 1),
            "median_days": round(float(median(wait_days)), 1),
            "min_days": min(wait_days),
            "max_days": max(wait_days),
        }
    )


def calculate_wait_time_metrics(
    queryset: QuerySet[CandidateProfile] | None = None,
) -> dict[str, Any]:
    """Calculate wait-time statistics to JOINING_LETTER (ANAL-03, 7.1 D1).

    Priority for start baseline:
    1. TimelineEvent(event_type=OFFER_LETTER)
    2. Fallback: TimelineEvent(event_type=INTERVIEW)
    3. Fallback: CandidateProfile.offer_letter_date
    4. Fallback: CandidateProfile.interview_date

    End milestone:
    TimelineEvent(event_type=JOINING_LETTER)

    Returns:
        baseline, baseline_source_counts, average_days, median_days, min_days,
        max_days, sample_size. If valid sample_size < ANALYTICS_MIN_COHORT_SIZE,
        returns the suppressed payload.
    """
    profiles = queryset if queryset is not None else CandidateProfile.objects.all()

    jl_date_map = _earliest_by_candidate(profiles, [TimelineEvent.EventType.JOINING_LETTER])
    if not jl_date_map:
        return suppression_payload()

    relevant_candidate_ids = list(jl_date_map.keys())

    offer_event_map = _earliest_by_candidate(
        CandidateProfile.objects.filter(id__in=relevant_candidate_ids),
        [TimelineEvent.EventType.OFFER_LETTER],
    )
    interview_event_map = _earliest_by_candidate(
        CandidateProfile.objects.filter(id__in=relevant_candidate_ids),
        [TimelineEvent.EventType.INTERVIEW],
    )

    profile_dates = {
        row["id"]: row
        for row in CandidateProfile.objects.filter(id__in=relevant_candidate_ids).values(
            "id", "offer_letter_date", "interview_date"
        )
    }

    wait_days_list: list[int] = []
    source_counts = {
        SOURCE_OFFER_LETTER_EVENT: 0,
        SOURCE_INTERVIEW_EVENT: 0,
        SOURCE_PROFILE_OFFER_DATE: 0,
        SOURCE_PROFILE_INTERVIEW_DATE: 0,
    }

    for cid, jl_date in jl_date_map.items():
        start_date: date | None = None
        source: str | None = None

        # Priority 1: TimelineEvent OFFER_LETTER
        if cid in offer_event_map:
            start_date = offer_event_map[cid]
            source = SOURCE_OFFER_LETTER_EVENT
        # Priority 2: TimelineEvent INTERVIEW
        elif cid in interview_event_map:
            start_date = interview_event_map[cid]
            source = SOURCE_INTERVIEW_EVENT
        # Priority 3: CandidateProfile offer_letter_date
        elif cid in profile_dates and profile_dates[cid]["offer_letter_date"]:
            start_date = profile_dates[cid]["offer_letter_date"]
            source = SOURCE_PROFILE_OFFER_DATE
        # Priority 4: CandidateProfile interview_date
        elif cid in profile_dates and profile_dates[cid]["interview_date"]:
            start_date = profile_dates[cid]["interview_date"]
            source = SOURCE_PROFILE_INTERVIEW_DATE

        # A JL that precedes its baseline is corrupted data, not a negative wait,
        # so the candidate is dropped rather than clamped (7.1 D1).
        if start_date is not None and source and jl_date >= start_date:
            wait_days_list.append((jl_date - start_date).days)
            source_counts[source] += 1

    return _wait_time_payload(wait_days_list, BASELINE_OFFER_LETTER, source_counts)


def calculate_survey_wait_time_metrics(
    queryset: QuerySet[CandidateProfile] | None = None,
) -> dict[str, Any]:
    """Calculate wait-time statistics from READINESS_SURVEY to JOINING_LETTER (7.2 D-13).

    This is ANAL-03's literal baseline ("between survey submission and joining
    letter issuance") and T7.7's ("between READINESS_SURVEY and JOINING_LETTER
    events"). It is published **alongside** the offer-letter metric rather than
    replacing it: the readiness survey is later than the offer, so the two measure
    materially different intervals, and `12_SEED_DATA` gives only ~20% of the
    cohort a survey event — the offer metric is what keeps a usable sample.

    The survey has no profile-date counterpart (CandidateProfile has no survey date
    column), so there is exactly one source: the earliest READINESS_SURVEY event.

    Returns:
        The same metric shape as `calculate_wait_time_metrics`, with
        `baseline: "READINESS_SURVEY"`, or the suppressed payload when its own
        sample is below the threshold.
    """
    profiles = queryset if queryset is not None else CandidateProfile.objects.all()

    jl_date_map = _earliest_by_candidate(profiles, [TimelineEvent.EventType.JOINING_LETTER])
    if not jl_date_map:
        return suppression_payload()

    survey_date_map = _earliest_by_candidate(
        CandidateProfile.objects.filter(id__in=list(jl_date_map.keys())),
        [TimelineEvent.EventType.READINESS_SURVEY],
    )

    wait_days_list: list[int] = []
    for cid, jl_date in jl_date_map.items():
        start_date = survey_date_map.get(cid)
        if start_date is not None and jl_date >= start_date:
            wait_days_list.append((jl_date - start_date).days)

    source_counts = {SOURCE_READINESS_SURVEY_EVENT: len(wait_days_list)}
    return _wait_time_payload(wait_days_list, BASELINE_READINESS_SURVEY, source_counts)


def get_public_stats() -> dict[str, Any]:
    """Landing-page KPI counters (04 §80, 7.2 D-09).

    Deliberately its own endpoint rather than a re-served analytics overview: §80's
    keys are three cross-app counts, not recruitment cohorts, so folding them into
    the analytics payload would either deviate from §80's documented shape or make
    the analytics app read community tables to fill a landing page.

    No `<5` floor applies — these are whole-population counts with no cohort
    dimension to slice, so a small number here is not a re-identification risk.
    """
    from apps.community.models import Post

    return _with_metadata(
        {
            "data_source": DATA_SOURCE_LABEL,
            "disclaimer": DISCLAIMER_TEXT,
            "registered_candidates": CandidateProfile.objects.count(),
            "community_posts": Post.objects.filter(is_deleted=False).count(),
            "timeline_events": TimelineEvent.objects.count(),
        }
    )
