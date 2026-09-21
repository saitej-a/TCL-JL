"""Structural invariants — the sync tables must never drift from the 3.1
state machine. These run without DB access and guard future edits."""

from apps.candidates.models import CandidateProfile
from apps.candidates.services import ALLOWED_TRANSITIONS
from apps.timeline.models import TimelineEvent
from apps.timeline.services import CHAIN_ORDER, EVENT_TYPE_TO_STATUS

S = CandidateProfile.Status


def test_chain_order_pairs_are_all_legal_edges():
    """Every consecutive CHAIN_ORDER pair is an ALLOWED_TRANSITIONS edge — the
    walk-the-chain algorithm is only sound while this holds (R2 guard)."""
    for i in range(len(CHAIN_ORDER) - 1):
        current, nxt = CHAIN_ORDER[i], CHAIN_ORDER[i + 1]
        assert nxt in ALLOWED_TRANSITIONS[current], (current, nxt)


def test_chain_order_starts_registered_ends_joined():
    assert CHAIN_ORDER[0] == S.REGISTERED
    assert CHAIN_ORDER[-1] == S.JOINED
    assert len(CHAIN_ORDER) == 9  # 11 statuses minus OTHER/WITHDRAWN


def test_mapping_targets_are_chain_statuses():
    for target in EVENT_TYPE_TO_STATUS.values():
        assert target in CHAIN_ORDER


def test_mapping_targets_exclude_other_and_withdrawn():
    assert S.OTHER not in EVENT_TYPE_TO_STATUS.values()
    assert S.WITHDRAWN not in EVENT_TYPE_TO_STATUS.values()


def test_mapped_event_types_are_real_choices():
    valid = set(TimelineEvent.EventType.values)
    for event_type in EVENT_TYPE_TO_STATUS:
        assert event_type in valid
    # OTHER is a real choice but deliberately unmapped (PATCH-only status moves).
    assert "OTHER" not in EVENT_TYPE_TO_STATUS
