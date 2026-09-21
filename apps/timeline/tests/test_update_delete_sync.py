"""update/delete timeline event tests — D2 forward-only semantics."""

from datetime import date

import pytest

from apps.candidates.models import CandidateProfile
from apps.candidates.services import InvalidTransitionError
from apps.timeline.models import TimelineEvent
from apps.timeline.services import (
    delete_timeline_event,
    record_timeline_event,
    update_timeline_event,
)

pytestmark = pytest.mark.django_db

D = date(2026, 9, 18)
D2 = date(2026, 9, 20)


def _seed(profile):
    """INTERVIEW + JOINING_LETTER → status JOINING_LETTER_RECEIVED."""
    record_timeline_event(profile, event_type="INTERVIEW", event_date=D)
    record_timeline_event(profile, event_type="JOINING_LETTER", event_date=D2)
    profile.refresh_from_db()
    return profile


def test_forward_type_edit_walks_status(make_profile):
    profile = _seed(make_profile())
    event = profile.timeline_events.get(event_type="JOINING_LETTER")
    update_timeline_event(event, {"event_type": "JOINED"})
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINED


def test_unmapped_to_mapped_edit_syncs(make_profile):
    profile = make_profile()  # REGISTERED, one OTHER event saved first
    event = record_timeline_event(profile, event_type="OTHER", event_date=D)
    update_timeline_event(event, {"event_type": "INTERVIEW"})
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.INTERVIEWED


def test_mapped_to_other_edit_never_syncs(make_profile):
    profile = _seed(make_profile())
    event = profile.timeline_events.get(event_type="INTERVIEW")
    update_timeline_event(event, {"event_type": "OTHER"})
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINING_LETTER_RECEIVED
    event.refresh_from_db()
    assert event.event_type == "OTHER"  # type change persisted, status untouched


def test_date_description_edit_leaves_status(make_profile):
    profile = _seed(make_profile())
    event = profile.timeline_events.get(event_type="INTERVIEW")
    update_timeline_event(event, {"event_date": D2, "description": "Panel was friendly."})
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINING_LETTER_RECEIVED
    event.refresh_from_db()
    assert event.event_date == D2
    assert event.description == "Panel was friendly."


def test_backwards_type_edit_is_forward_only_noop(make_profile):
    """Editing JOINING_LETTER → INTERVIEW (an earlier milestone) persists the new
    type but never regresses the status (D2)."""
    profile = _seed(make_profile())
    event = profile.timeline_events.get(event_type="JOINING_LETTER")
    update_timeline_event(event, {"event_type": "INTERVIEW"})
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINING_LETTER_RECEIVED
    event.refresh_from_db()
    assert event.event_type == "INTERVIEW"


def test_blocked_type_edit_rolls_back_whole_update(make_profile):
    """OTHER profile + pre-WAITING-target edit: chain blocked → the type change
    is rolled back too (all-or-nothing update)."""
    profile = make_profile(current_status=CandidateProfile.Status.OTHER)
    event = record_timeline_event(
        profile, event_type="OTHER", event_date=D, auto_update_status=False
    )
    with pytest.raises(InvalidTransitionError) as excinfo:
        update_timeline_event(event, {"event_type": "INTERVIEW"})
    assert excinfo.value.code == "status_invalid_transition"
    event.refresh_from_db()
    assert event.event_type == "OTHER"  # edit rolled back
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.OTHER


def test_delete_never_touches_status(make_profile):
    profile = _seed(make_profile())
    event = profile.timeline_events.get(event_type="JOINING_LETTER")
    delete_timeline_event(event)
    assert not TimelineEvent.objects.filter(pk=event.pk).exists()
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINING_LETTER_RECEIVED
