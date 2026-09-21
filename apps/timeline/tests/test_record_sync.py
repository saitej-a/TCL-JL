"""record_timeline_event tests — D1 walk-the-chain sync matrix + atomicity (04 §85)."""

from datetime import date

import pytest

from apps.candidates.models import CandidateProfile
from apps.candidates.services import InvalidTransitionError
from apps.timeline.models import TimelineEvent
from apps.timeline.services import record_timeline_event

pytestmark = pytest.mark.django_db

D = date(2026, 9, 18)


def test_each_mapped_type_advances_status(make_profile):
    """Each of the 7 mapped types drives its status (fresh profile, single hop
    or multi-hop — the walk handles both identically)."""
    cases = {
        "INTERVIEW": CandidateProfile.Status.INTERVIEWED,
        "SELECTION": CandidateProfile.Status.SELECTED,
        "OFFER_LETTER": CandidateProfile.Status.OFFER_RECEIVED,
        "READINESS_SURVEY": CandidateProfile.Status.READINESS_SURVEY,
        "JOINING_LETTER": CandidateProfile.Status.JOINING_LETTER_RECEIVED,
        "JOINING_DATE": CandidateProfile.Status.JOINING_DATE_RECEIVED,
        "JOINED": CandidateProfile.Status.JOINED,
    }
    for event_type, expected_status in cases.items():
        profile = make_profile()  # fresh REGISTERED profile per case
        record_timeline_event(profile, event_type=event_type, event_date=D)
        profile.refresh_from_db()
        assert profile.current_status == expected_status, event_type


def test_at_target_is_idempotent_noop(make_profile):
    profile = make_profile()
    record_timeline_event(profile, event_type="INTERVIEW", event_date=D)
    record_timeline_event(profile, event_type="INTERVIEW", event_date=D)  # same target again
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.INTERVIEWED
    assert TimelineEvent.objects.count() == 2  # both events persist


def test_past_target_backfilled_noop(make_profile):
    """SELECTION recorded while already OFFER_RECEIVED: backfilled milestone —
    status stays put (forward-only), event still saved."""
    profile = make_profile()
    record_timeline_event(profile, event_type="OFFER_LETTER", event_date=D)
    record_timeline_event(profile, event_type="SELECTION", event_date=D)  # earlier milestone
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.OFFER_RECEIVED
    assert TimelineEvent.objects.count() == 2


def test_terminal_blocked_rolls_back_event_row(make_profile):
    """D1's own example: JOINED reached, INTERVIEW arrives late → the chain is
    blocked; the raise rolls back the event insert (04 §85: both writes or none)."""
    profile = make_profile()
    record_timeline_event(profile, event_type="JOINED", event_date=D)
    with pytest.raises(InvalidTransitionError) as excinfo:
        record_timeline_event(profile, event_type="INTERVIEW", event_date=D)
    assert excinfo.value.code == "status_terminal"
    assert TimelineEvent.objects.count() == 1  # second insert rolled back
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINED


def test_withdrawn_blocked_for_any_event(make_profile):
    profile = make_profile(current_status=CandidateProfile.Status.WITHDRAWN)
    with pytest.raises(InvalidTransitionError) as excinfo:
        record_timeline_event(profile, event_type="JOINED", event_date=D)
    assert excinfo.value.code == "status_terminal"
    assert TimelineEvent.objects.count() == 0


def test_other_as_current_blocks_pre_waiting_target(make_profile):
    profile = make_profile(current_status=CandidateProfile.Status.OTHER)
    with pytest.raises(InvalidTransitionError) as excinfo:
        record_timeline_event(profile, event_type="INTERVIEW", event_date=D)
    assert excinfo.value.code == "status_invalid_transition"
    assert TimelineEvent.objects.count() == 0  # rolled back


def test_other_as_current_allows_waiting_or_later(make_profile):
    profile = make_profile(current_status=CandidateProfile.Status.OTHER)
    record_timeline_event(profile, event_type="JOINING_LETTER", event_date=D)
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINING_LETTER_RECEIVED


def test_other_event_type_never_syncs_status(make_profile):
    profile = make_profile()
    record_timeline_event(profile, event_type="OTHER", event_date=D)
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.REGISTERED
    assert TimelineEvent.objects.count() == 1  # row saved, status untouched


def test_auto_update_status_false_skips_sync(make_profile):
    profile = make_profile()
    record_timeline_event(profile, event_type="JOINED", event_date=D, auto_update_status=False)
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.REGISTERED
    assert TimelineEvent.objects.count() == 1


def test_event_and_status_commit_together(make_profile):
    """04 §85 happy path: one transaction produces both the row and the hops."""
    profile = make_profile()
    event = record_timeline_event(profile, event_type="SELECTION", event_date=D)
    event.refresh_from_db()
    assert TimelineEvent.objects.filter(pk=event.pk).exists()
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.SELECTED
