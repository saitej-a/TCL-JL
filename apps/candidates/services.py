"""Status transition service (T3.2; 3.1 D1/D2) and profile create/update
lifecycle (T3.4-T3.5; 3.2 D1/D4).

Client-submitted statuses are never trusted: every change goes through
``transition_status``. Seam note for 4.1 (TIME-02): status changes will be
wrapped with timeline-event creation inside one atomic transaction there —
keep this function the single mutation point.
"""

from django.db import IntegrityError, transaction

from apps.candidates.models import CandidateProfile

S = CandidateProfile.Status

# 03 §6 diagram edges, exactly (3.1 D2). Same-status is a no-op handled in
# transition_status; WITHDRAWN is not listed because D1 makes it reachable
# from any non-terminal status via the terminal rule below.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    S.REGISTERED: {S.INTERVIEWED},
    S.INTERVIEWED: {S.SELECTED},
    S.SELECTED: {S.OFFER_RECEIVED, S.OTHER},
    S.OFFER_RECEIVED: {S.READINESS_SURVEY, S.OTHER},
    S.READINESS_SURVEY: {S.WAITING_FOR_JOINING_LETTER, S.OTHER},
    S.WAITING_FOR_JOINING_LETTER: {S.JOINING_LETTER_RECEIVED, S.OTHER},
    S.JOINING_LETTER_RECEIVED: {S.JOINING_DATE_RECEIVED},
    S.JOINING_DATE_RECEIVED: {S.JOINED},
    S.OTHER: {S.WAITING_FOR_JOINING_LETTER},
    S.JOINED: set(),
    S.WITHDRAWN: set(),
}

TERMINAL_STATUSES = {S.JOINED, S.WITHDRAWN}


class ProfileAlreadyExistsError(Exception):
    """A user may own at most one profile (T3.4); rendered as 409 by the view."""

    code = "profile_exists"


class InvalidTransitionError(ValueError):
    """Raised for illegal status moves; code rides the exception (3.2 renders 400)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def transition_status(profile: CandidateProfile, new_status: str) -> CandidateProfile:
    """Move ``profile`` to ``new_status`` iff the edge is legal (D2).

    Same-status calls are idempotent no-ops (no save, no updated_at bump).
    WITHDRAWN is accepted from any non-terminal status (D1) and is terminal.
    """
    current = profile.current_status
    if current == new_status:
        return profile  # idempotent

    if current in TERMINAL_STATUSES:
        raise InvalidTransitionError(
            "status_terminal",
            f"Status '{current}' is terminal; no further transitions are allowed.",
        )

    if new_status == S.WITHDRAWN:
        allowed = True  # D1: WITHDRAWN reachable from any non-terminal status
    else:
        allowed = new_status in ALLOWED_TRANSITIONS.get(current, set())

    if not allowed:
        raise InvalidTransitionError(
            "status_invalid_transition",
            f"Cannot move from '{current}' to '{new_status}'.",
        )

    profile.current_status = new_status
    profile.save(update_fields=["current_status", "updated_at"])
    # 4.1 seam: atomic timeline-event creation wraps this mutation (TIME-02).
    return profile


def create_profile(user, data: dict, requested_status: str | None = None) -> CandidateProfile:
    """Create a profile pinned REGISTERED, then honor a requested status (3.2 D1)
    — all inside one transaction. An illegal requested status raises
    ``InvalidTransitionError`` and rolls back creation: no profile row survives
    a failed POST. Duplicate creation (T3.4) raises ``ProfileAlreadyExistsError``
    (IntegrityError caught race-safe)."""
    try:
        with transaction.atomic():
            profile = CandidateProfile.objects.create(
                user=user, current_status=CandidateProfile.Status.REGISTERED, **data
            )
            if requested_status and requested_status != CandidateProfile.Status.REGISTERED:
                transition_status(profile, requested_status)
            return profile
    except IntegrityError:
        raise ProfileAlreadyExistsError() from None


# --- Profile completeness (T4.8; 4.2 R1) ----------------------------------------

#: Enrichment fields a candidate can fill after onboarding. Structural (not a
#: setting): these are the profile's optional fields, and changing them is a
#: product decision, not a deployment knob.
PROFILE_COMPLETION_FIELDS: tuple[str, ...] = (
    "interview_center",
    "interview_date",
    "offer_letter_date",
    "joining_location",
    "expected_joining_date",
)

#: One item per enrichment field, plus "status advanced past REGISTERED" and
#: "has recorded at least one milestone". Equal weights.
PROFILE_COMPLETION_ITEMS = len(PROFILE_COMPLETION_FIELDS) + 2


def compute_profile_completion(profile: CandidateProfile, *, has_events: bool = False) -> int:
    """Percentage of the completion checklist satisfied (4.2 R1), rounded to an
    integer.

    Identity fields (``display_name``, ``public_identity_mode``) are excluded
    **by design**: anonymity is a legitimate privacy choice (3.1 D1), so a
    candidate who never shares a name must still be able to reach 100% — a
    completeness meter must not pressure candidates into identifying
    themselves.

    ``has_events`` is a parameter rather than an import because timeline models
    import this module, so reaching back would invert 4.1's pinned
    ``timeline -> candidates`` direction.
    """
    filled = 0
    for field in PROFILE_COMPLETION_FIELDS:
        value = getattr(profile, field, None)
        if isinstance(value, str):
            filled += 1 if value.strip() else 0
        elif value is not None:
            filled += 1
    if profile.current_status != S.REGISTERED:
        filled += 1
    if has_events:
        filled += 1
    return round(100 * filled / PROFILE_COMPLETION_ITEMS)


def update_profile(profile: CandidateProfile, data: dict) -> CandidateProfile:
    """Apply self-editable field changes and an optional status move atomically
    (04 §21): a rejected transition rolls back the field saves in the same
    PATCH. Status changes still flow only through ``transition_status``."""
    requested_status = data.pop("current_status", None)
    with transaction.atomic():
        for field, value in data.items():
            setattr(profile, field, value)
        if data:
            profile.save(update_fields=[*data.keys(), "updated_at"])
        if requested_status is not None and requested_status != profile.current_status:
            transition_status(profile, requested_status)
    profile.refresh_from_db()
    return profile
