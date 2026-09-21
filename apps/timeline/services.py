"""Timeline services (T4.3; 4.1 D1/D2, R1–R3) — milestone recording with atomic
status synchronization (TIME-02).

`record_timeline_event` is the write path 04 §24–27 endpoints (Phase 4.2) call.
Every status mutation still flows through `apps.candidates.services.transition_status`
(the single mutation point), wrapped in the same transaction as the event insert —
either both commit or neither does (04 §85).

Sync policy (D1 "walk-the-chain"): the event's mapped target status is reached by
walking consecutive legal edges, so backfilled out-of-order milestones multi-hop
forward. At/past the target is an idempotent no-op; genuinely blocked chains raise
`InvalidTransitionError` and roll back the insert. D2: edits re-sync forward only —
deleting or re-dating events never regresses the candidate's status.
"""

from django.db import transaction

from apps.candidates.models import CandidateProfile
from apps.candidates.services import InvalidTransitionError, transition_status
from apps.timeline.models import TimelineEvent

S = CandidateProfile.Status

# The 9 chain statuses in edge order (3.1 D2 forward chain). Every consecutive
# pair is a legal ALLOWED_TRANSITIONS edge — asserted by test_walk_invariants.
CHAIN_ORDER: tuple[str, ...] = (
    S.REGISTERED,
    S.INTERVIEWED,
    S.SELECTED,
    S.OFFER_RECEIVED,
    S.READINESS_SURVEY,
    S.WAITING_FOR_JOINING_LETTER,
    S.JOINING_LETTER_RECEIVED,
    S.JOINING_DATE_RECEIVED,
    S.JOINED,
)

# Event type → target status (D1). OTHER events carry no status semantics, and no
# event maps to OTHER/WITHDRAWN — those moves stay PATCH-only (3.2 update_profile).
EVENT_TYPE_TO_STATUS: dict[str, str] = {
    TimelineEvent.EventType.INTERVIEW: S.INTERVIEWED,
    TimelineEvent.EventType.SELECTION: S.SELECTED,
    TimelineEvent.EventType.OFFER_LETTER: S.OFFER_RECEIVED,
    TimelineEvent.EventType.READINESS_SURVEY: S.READINESS_SURVEY,
    TimelineEvent.EventType.JOINING_LETTER: S.JOINING_LETTER_RECEIVED,
    TimelineEvent.EventType.JOINING_DATE: S.JOINING_DATE_RECEIVED,
    TimelineEvent.EventType.JOINED: S.JOINED,
}


def _walk_status(profile: CandidateProfile, target: str) -> None:
    """Advance `profile.current_status` to `target` along legal edges (D1).

    Runs inside the caller's transaction: any raise aborts the surrounding
    atomic block, so the event insert and every hop roll back together.
    """
    current = profile.current_status
    if current == target:
        return  # idempotent — includes same-status terminal states

    if current in (S.JOINED, S.WITHDRAWN):
        # Terminal, and a different target was requested: blocked (D1's JOINED
        # + late INTERVIEW example). Nothing about a terminal status moves.
        raise InvalidTransitionError(
            "status_terminal",
            f"Status '{current}' is terminal; timeline events cannot change it.",
        )

    if current == S.OTHER:
        # Only OTHER → WAITING_FOR_JOINING_LETTER re-enters the chain (3.1 D2);
        # anything earlier than WAITING is unreachable from OTHER.
        waiting_idx = CHAIN_ORDER.index(S.WAITING_FOR_JOINING_LETTER)
        if target not in CHAIN_ORDER or CHAIN_ORDER.index(target) < waiting_idx:
            raise InvalidTransitionError(
                "status_invalid_transition",
                f"Cannot reach '{target}' from '{S.OTHER}'.",
            )
        path = list(CHAIN_ORDER[waiting_idx : CHAIN_ORDER.index(target) + 1])
    else:
        current_idx, target_idx = CHAIN_ORDER.index(current), CHAIN_ORDER.index(target)
        if current_idx > target_idx:
            return  # at/past the target: backfilled milestone, status unchanged
        path = list(CHAIN_ORDER[current_idx + 1 : target_idx + 1])

    for step in path:
        # Re-validates each hop; a failure here rolls back everything above.
        transition_status(profile, step)


def record_timeline_event(
    candidate: CandidateProfile,
    *,
    event_type: str,
    event_date,
    description: str = "",
    is_verified: bool = False,
    auto_update_status: bool = True,
) -> TimelineEvent:
    """Persist a milestone and (opt-in, default on — T4.3 R1) sync the
    candidate's status to the event's mapped target — atomically (04 §85).

    Unmapped event types (OTHER) save the row without touching status. Blocked
    chains raise `InvalidTransitionError`; the event row is rolled back with the
    status hops (no partial state is ever observable).
    """
    with transaction.atomic():
        event = TimelineEvent.objects.create(
            candidate=candidate,
            event_type=event_type,
            event_date=event_date,
            description=description,
            is_verified=is_verified,
        )
        if auto_update_status:
            target = EVENT_TYPE_TO_STATUS.get(event_type)
            if target is not None:
                _walk_status(candidate, target)
    event.refresh_from_db()
    return event


def update_timeline_event(event: TimelineEvent, data: dict) -> TimelineEvent:
    """Apply field edits atomically; re-run forward sync when `event_type`
    changes to a mapped type (D2). A blocked re-sync rolls the whole update
    back — type change included. Date/description edits never touch status,
    and no edit path ever regresses it.
    """
    new_type = data.pop("event_type", None)
    with transaction.atomic():
        type_changed = new_type is not None and new_type != event.event_type
        update_fields = [*data.keys(), "updated_at"]
        for field, value in data.items():
            setattr(event, field, value)
        if type_changed:
            event.event_type = new_type
            update_fields.append("event_type")
        if update_fields != ["updated_at"]:
            event.save(update_fields=update_fields)
        if type_changed:
            target = EVENT_TYPE_TO_STATUS.get(new_type)
            if target is not None:
                _walk_status(event.candidate, target)
    event.refresh_from_db()
    return event


def delete_timeline_event(event: TimelineEvent) -> None:
    """Remove an event; the candidate's status is forward-only history and is
    never recalculated on deletion (D2)."""
    event.delete()
