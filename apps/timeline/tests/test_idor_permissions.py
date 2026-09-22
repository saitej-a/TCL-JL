"""T4.7 — `IsTimelineOwner` and the query-scoping layer (06 §4.2-§4.3.3, 04 §88-§89).

4.2 ships **two independent** ownership layers and this file proves each one on
its own:

1. **Query scoping** — every queryset filters `candidate__user=request.user`, so a
   foreign identifier cannot resolve even if the permission class were miswired.
2. **`IsTimelineOwner`** — the object-level rule from 06 §4.3.3, unit-tested here
   so it stays a real guard rather than decorative configuration.

Either layer alone stops the attack, which is the point: one mistake is not a
breach. Layer 2's unit tests use a minimal request stub carrying just `.user`,
because that is the entire surface the permission class is allowed to touch.
"""

from datetime import date

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.candidates.models import CandidateProfile
from apps.timeline.models import TimelineEvent
from apps.timeline.permissions import IsTimelineOwner

pytestmark = pytest.mark.django_db

COLLECTION = "/api/v1/timeline/"
PAST = date(2026, 9, 18)


class _StubRequest:
    """The only thing `has_object_permission` may rely on: `request.user`."""

    def __init__(self, user):
        self.user = user


def test_is_timeline_owner_allows_owner(make_user, make_profile, make_event):
    profile = make_profile(user=make_user())
    event = make_event(profile)

    assert IsTimelineOwner().has_object_permission(_StubRequest(profile.user), None, event) is True


def test_is_timeline_owner_denies_other_user(make_user, make_profile, make_event):
    event = make_event(make_profile(user=make_user()))

    assert IsTimelineOwner().has_object_permission(_StubRequest(make_user()), None, event) is False


def test_is_timeline_owner_denies_anonymous(make_user, make_profile, make_event):
    event = make_event(make_profile(user=make_user()))

    assert (
        IsTimelineOwner().has_object_permission(_StubRequest(AnonymousUser()), None, event) is False
    )


def test_is_timeline_owner_denies_profile_less_candidate(make_profile, make_event):
    """3.1 D4's older truth: profiles can outlive their account link (SET_NULL),
    so a candidate with `user_id = None` must not be owned by anyone."""
    orphan = CandidateProfile.objects.create(
        user=None, batch="2025", hiring_type="DIGITAL", region="Telangana"
    )
    event = TimelineEvent.objects.create(candidate=orphan, event_type="INTERVIEW", event_date=PAST)

    assert IsTimelineOwner().has_object_permission(_StubRequest(None), None, event) is False


def test_layer_one_scoping_hides_foreign_events_from_every_read(
    make_user, make_profile, make_event, auth_api
):
    """Layer 1 isolated over HTTP: none of the victim's identifiers appear in any
    response the attacker can obtain — list, or filter that matches only the
    victim's rows."""
    victim = make_profile(user=make_user())
    attacker = make_profile(user=make_user())
    victim_events = [
        make_event(victim, event_type="JOINING_LETTER"),
        make_event(victim, event_type="JOINED"),
    ]
    make_event(attacker, event_type="INTERVIEW")
    client = auth_api(attacker.user)

    bodies = [
        client.get(COLLECTION).content.decode(),
        client.get(f"{COLLECTION}?event_type=JOINING_LETTER").content.decode(),
        client.get(f"{COLLECTION}?event_type=JOINED").content.decode(),
    ]

    for body in bodies:
        assert all(str(event.id) not in body for event in victim_events)
        assert str(victim.id) not in body


def test_cross_candidate_writes_leave_the_victim_untouched(
    make_user, make_profile, make_event, auth_api
):
    """Both mutating verbs against a real foreign UUID: no row changes, no status
    changes, and the attacker learns nothing (404, never 403 — 06 §4.2.2)."""
    victim = make_profile(user=make_user())
    attacker = make_profile(user=make_user())
    event = make_event(victim, event_type="OTHER", description="original")
    client = auth_api(attacker.user)
    url = f"{COLLECTION}{event.id}/"

    assert client.patch(url, {"description": "hijacked"}).status_code == 404
    assert client.delete(url).status_code == 404

    event.refresh_from_db()
    assert event.description == "original"
    victim.refresh_from_db()
    assert victim.current_status == CandidateProfile.Status.REGISTERED
    assert TimelineEvent.objects.filter(candidate=victim).count() == 1


def test_permission_denial_is_never_a_403_for_foreign_objects(
    make_user, make_profile, make_event, auth_api
):
    """06 §4.2.2: returning 403 would confirm the UUID exists. 404 only."""
    victim = make_profile(user=make_user())
    attacker = make_profile(user=make_user())
    event = make_event(victim)

    response = auth_api(attacker.user).delete(f"{COLLECTION}{event.id}/")
    missing = auth_api(attacker.user).delete(f"{COLLECTION}00000000-0000-4000-8000-000000000001/")

    assert response.status_code == missing.status_code == 404
    assert response.content == missing.content
