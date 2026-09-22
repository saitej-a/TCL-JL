"""PATCH/DELETE /api/v1/timeline/{event_id}/ — T4.6-T4.7 (04 §26-§27, 06 §4.2).

The defining property of this file: a foreign UUID and a nonexistent UUID must be
**indistinguishable** — same status, same code, same bytes. Anything that
distinguishes them tells an attacker which identifiers exist (04 §89).
"""

from datetime import date, timedelta

import pytest

from apps.candidates.models import CandidateProfile
from apps.timeline.models import TimelineEvent

pytestmark = pytest.mark.django_db

COLLECTION = "/api/v1/timeline/"
TODAY = date.today()
PAST = date(2026, 9, 18)


def _url(event) -> str:
    return f"{COLLECTION}{event.id}/"


def test_detail_read_is_not_part_of_the_surface(make_user, make_profile, make_event, auth_api):
    """04 §24 lists no `GET /{id}/` — the collection route is the read path."""
    profile = make_profile(user=make_user())
    event = make_event(profile)

    response = auth_api(profile.user).get(_url(event))

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_put_is_not_allowed(make_user, make_profile, make_event, auth_api):
    """04 §26 is a partial update; a full-replace PUT is not in the surface."""
    profile = make_profile(user=make_user())
    event = make_event(profile)

    response = auth_api(profile.user).put(_url(event), {"event_type": "INTERVIEW"})

    assert response.status_code == 405


def test_patch_date_and_description_leaves_status_alone(
    make_user, make_profile, make_event, auth_api
):
    profile = make_profile(user=make_user(), current_status=CandidateProfile.Status.OFFER_RECEIVED)
    event = make_event(profile, event_type="INTERVIEW", event_date=PAST)

    response = auth_api(profile.user).patch(
        _url(event), {"event_date": "2026-09-19", "description": "Updated information."}
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated information."
    event.refresh_from_db()
    assert event.event_date == date(2026, 9, 19)
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.OFFER_RECEIVED


def test_patch_event_type_resyncs_forward(make_user, make_profile, make_event, auth_api):
    """4.1 D2: a type edit re-runs the walk toward the new mapped target."""
    profile = make_profile(user=make_user())
    event = make_event(profile, event_type="OTHER", event_date=PAST)

    response = auth_api(profile.user).patch(_url(event), {"event_type": "SELECTION"})

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.SELECTED


def test_patch_to_blocked_type_rolls_back_the_type_change(
    make_user, make_profile, make_event, auth_api
):
    profile = make_profile(user=make_user(), current_status=CandidateProfile.Status.JOINED)
    event = make_event(profile, event_type="OTHER", event_date=PAST)

    response = auth_api(profile.user).patch(_url(event), {"event_type": "INTERVIEW"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "status_terminal"
    event.refresh_from_db()
    assert event.event_type == "OTHER"  # type change rolled back with the walk


def test_patch_date_outside_horizon_is_rejected(make_user, make_profile, make_event, auth_api):
    profile = make_profile(user=make_user())
    event = make_event(profile)

    response = auth_api(profile.user).patch(
        _url(event), {"event_date": (TODAY + timedelta(days=731)).isoformat()}
    )

    assert response.status_code == 400
    assert "event_date" in response.json()


def test_patch_joining_letter_to_future_date_is_rejected(
    make_user, make_profile, make_event, auth_api
):
    """D3's carve-out must also apply when only the date is edited — the
    effective type comes from the stored row in that case."""
    profile = make_profile(user=make_user())
    event = make_event(profile, event_type="JOINING_LETTER", event_date=PAST)

    response = auth_api(profile.user).patch(
        _url(event), {"event_date": (TODAY + timedelta(days=3)).isoformat()}
    )

    assert response.status_code == 400
    assert "event_date" in response.json()


def test_delete_own_event(make_user, make_profile, make_event, auth_api):
    profile = make_profile(user=make_user(), current_status=CandidateProfile.Status.JOINED)
    event = make_event(profile)

    response = auth_api(profile.user).delete(_url(event))

    assert response.status_code == 204
    assert not TimelineEvent.objects.filter(id=event.id).exists()
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINED  # forward-only (D2)


def test_cannot_patch_another_candidates_event(make_user, make_profile, make_event, auth_api):
    victim = make_profile(user=make_user())
    attacker = make_profile(user=make_user())
    event = make_event(victim, event_type="INTERVIEW", event_date=PAST)

    response = auth_api(attacker.user).patch(_url(event), {"description": "Malicious modification"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "timeline_event_not_found"
    event.refresh_from_db()
    assert event.description == ""


def test_cannot_delete_another_candidates_event(make_user, make_profile, make_event, auth_api):
    victim = make_profile(user=make_user())
    attacker = make_profile(user=make_user())
    event = make_event(victim)

    response = auth_api(attacker.user).delete(_url(event))

    assert response.status_code == 404
    assert TimelineEvent.objects.filter(id=event.id).exists()


def test_idor_attempt_leaves_victim_status_untouched(make_user, make_profile, make_event, auth_api):
    victim = make_profile(user=make_user())
    attacker = make_profile(user=make_user())
    event = make_event(victim, event_type="OTHER", event_date=PAST)

    auth_api(attacker.user).patch(_url(event), {"event_type": "JOINED"})

    victim.refresh_from_db()
    assert victim.current_status == CandidateProfile.Status.REGISTERED


def test_foreign_and_nonexistent_uuids_are_indistinguishable(
    make_user, make_profile, make_event, auth_api
):
    """04 §89: identical status, code, message — and identical bytes."""
    victim = make_profile(user=make_user())
    attacker = make_profile(user=make_user())
    foreign = make_event(victim)
    client = auth_api(attacker.user)

    foreign_response = client.patch(_url(foreign), {"description": "x"})
    missing_response = client.patch(
        f"{COLLECTION}00000000-0000-4000-8000-000000000000/", {"description": "x"}
    )

    assert foreign_response.status_code == missing_response.status_code == 404
    assert foreign_response.content == missing_response.content


def test_anonymous_is_rejected(make_user, make_profile, make_event, api):
    profile = make_profile(user=make_user())
    event = make_event(profile)

    assert api.patch(_url(event), {"description": "x"}).status_code == 401
    assert api.delete(_url(event)).status_code == 401


def test_unverified_is_rejected(make_user, make_profile, make_event, make_unverified_user):
    from rest_framework.test import APIClient

    profile = make_profile(user=make_user())
    event = make_event(profile)
    client = APIClient()
    client.force_authenticate(user=make_unverified_user)

    assert client.delete(_url(event)).status_code == 403
    assert TimelineEvent.objects.filter(id=event.id).exists()


def test_profile_less_attacker_cannot_reach_events(make_user, make_profile, make_event, auth_api):
    """A user with no profile has no timeline of their own — and still cannot
    reach anyone else's (the scoping layer never consults the attacker's profile)."""
    victim = make_profile(user=make_user())
    event = make_event(victim)

    response = auth_api(make_user()).delete(_url(event))

    assert response.status_code == 404
    assert TimelineEvent.objects.filter(id=event.id).exists()
