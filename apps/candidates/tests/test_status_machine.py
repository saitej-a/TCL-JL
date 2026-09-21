"""Status machine tests (T3.2; 3.1 D1/D2) — the phase 'done when' gate."""

import pytest

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.candidates.services import (
    TERMINAL_STATUSES,
    InvalidTransitionError,
    S,
    transition_status,
)

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "Correct Horse Battery 9!"
FULL_CHAIN = [
    S.REGISTERED,
    S.INTERVIEWED,
    S.SELECTED,
    S.OFFER_RECEIVED,
    S.READINESS_SURVEY,
    S.WAITING_FOR_JOINING_LETTER,
    S.JOINING_LETTER_RECEIVED,
    S.JOINING_DATE_RECEIVED,
    S.JOINED,
]


def _make_profile(status=S.REGISTERED) -> CandidateProfile:
    user = User.objects.create_user(f"status-{status.lower()}@test.dev", VALID_PASSWORD)
    return CandidateProfile.objects.create(
        user=user, batch="2025", hiring_type="DIGITAL", region="Hyderabad", current_status=status
    )


class TestLegalTransitions:
    @pytest.mark.parametrize(
        "frm,to",
        [
            (S.REGISTERED, S.INTERVIEWED),
            (S.INTERVIEWED, S.SELECTED),
            (S.SELECTED, S.OFFER_RECEIVED),
            (S.OFFER_RECEIVED, S.READINESS_SURVEY),
            (S.READINESS_SURVEY, S.WAITING_FOR_JOINING_LETTER),
            (S.WAITING_FOR_JOINING_LETTER, S.JOINING_LETTER_RECEIVED),
            (S.JOINING_LETTER_RECEIVED, S.JOINING_DATE_RECEIVED),
            (S.JOINING_DATE_RECEIVED, S.JOINED),
            (S.SELECTED, S.OTHER),  # escape edges per 03 §6
            (S.OFFER_RECEIVED, S.OTHER),
            (S.READINESS_SURVEY, S.OTHER),
            (S.WAITING_FOR_JOINING_LETTER, S.OTHER),
            (S.OTHER, S.WAITING_FOR_JOINING_LETTER),  # the single reverse edge
        ],
    )
    def test_diagram_edge_allowed(self, frm, to):
        profile = _make_profile(frm)
        result = transition_status(profile, to)
        assert result.current_status == to
        profile.refresh_from_db()
        assert profile.current_status == to

    def test_full_forward_chain_walks_to_joined(self):
        profile = _make_profile()
        for status in FULL_CHAIN[1:]:
            profile = transition_status(profile, status)
        assert profile.current_status == S.JOINED


class TestWithdrawnTerminalRule:
    """D1: WITHDRAWN reachable from any non-terminal status, then final."""

    @pytest.mark.parametrize(
        "frm",
        [
            s
            for s in [
                S.REGISTERED,
                S.INTERVIEWED,
                S.SELECTED,
                S.OFFER_RECEIVED,
                S.READINESS_SURVEY,
                S.WAITING_FOR_JOINING_LETTER,
                S.JOINING_LETTER_RECEIVED,
                S.JOINING_DATE_RECEIVED,
                S.OTHER,
            ]
        ],
    )
    def test_withdrawn_reachable_from_every_non_terminal(self, frm):
        profile = _make_profile(frm)
        result = transition_status(profile, S.WITHDRAWN)
        assert result.current_status == S.WITHDRAWN

    def test_withdrawn_is_terminal(self):
        profile = _make_profile(S.WITHDRAWN)
        with pytest.raises(InvalidTransitionError) as exc:
            transition_status(profile, S.WAITING_FOR_JOINING_LETTER)
        assert exc.value.code == "status_terminal"

    def test_terminal_statuses_constant(self):
        assert TERMINAL_STATUSES == {S.JOINED, S.WITHDRAWN}


class TestRejectedTransitions:
    @pytest.mark.parametrize(
        "frm,to",
        [
            (S.REGISTERED, S.SELECTED),  # skip-ahead
            (S.REGISTERED, S.JOINED),  # skip-to-end
            (S.SELECTED, S.INTERVIEWED),  # backward
            (S.INTERVIEWED, S.OTHER),  # OTHER escape only from the four listed
            (S.WITHDRAWN, S.REGISTERED),  # resurrection from WITHDRAWN (D1 terminal)
            (S.WITHDRAWN, S.OTHER),  # WITHDRAWN has no outgoing edges
        ],
    )
    def test_non_edge_rejected(self, frm, to):
        profile = _make_profile(frm)
        with pytest.raises(InvalidTransitionError):
            transition_status(profile, to)
        profile.refresh_from_db()
        assert profile.current_status == frm  # unchanged

    def test_resurrection_from_joined_raises_terminal(self):
        """From JOINED the service reports the precise terminal code."""
        profile = _make_profile(S.JOINED)
        with pytest.raises(InvalidTransitionError) as exc:
            transition_status(profile, S.REGISTERED)
        assert exc.value.code == "status_terminal"

    def test_resurrection_from_withdrawn_raises_terminal(self):
        profile = _make_profile(S.WITHDRAWN)
        with pytest.raises(InvalidTransitionError) as exc:
            transition_status(profile, S.INTERVIEWED)
        assert exc.value.code == "status_terminal"

    def test_bogus_status_string_rejected_from_live_status(self):
        profile = _make_profile(S.INTERVIEWED)
        with pytest.raises(InvalidTransitionError) as exc:
            transition_status(profile, "BOGUS")
        assert exc.value.code == "status_invalid_transition"
        profile.refresh_from_db()
        assert profile.current_status == S.INTERVIEWED

    def test_rejection_does_not_mutate_db(self):
        profile = _make_profile(S.REGISTERED)
        with pytest.raises(InvalidTransitionError):
            transition_status(profile, S.JOINED)
        profile.refresh_from_db()
        assert profile.current_status == S.REGISTERED


class TestIdempotentNoOp:
    def test_same_status_returns_unchanged_without_update_bump(self):
        profile = _make_profile(S.INTERVIEWED)
        before = profile.updated_at
        result = transition_status(profile, S.INTERVIEWED)
        assert result.current_status == S.INTERVIEWED
        assert result.updated_at == before  # no save, no auto_now bump
