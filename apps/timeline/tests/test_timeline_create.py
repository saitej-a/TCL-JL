"""POST /api/v1/timeline/ — T4.5 create + sync + D3 date bounds (04 §25, §85).

The two invariants under test:

* **Atomicity over the wire** — a blocked chain must 400 *and* leave no event row
  (04 §85: the insert and the status hops commit or roll back together).
* **Ownership is never client-supplied** — `candidate` comes from `request.user`
  (06 §4.5), so ids in the body cannot retarget whose timeline grows.
"""

from datetime import date, timedelta

import pytest

from apps.candidates.models import CandidateProfile
from apps.timeline.models import TimelineEvent

pytestmark = pytest.mark.django_db

URL = "/api/v1/timeline/"
TODAY = date.today()
PAST = date(2026, 9, 18)
RESPONSE_KEYS = {"id", "event_type", "event_date", "description", "is_verified", "created_at"}


def test_create_returns_201_spec_shape(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "INTERVIEW", "event_date": PAST.isoformat(), "description": "Done."}
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == RESPONSE_KEYS
    assert body["event_type"] == "INTERVIEW"
    assert body["event_date"] == PAST.isoformat()
    assert body["description"] == "Done."
    assert body["is_verified"] is False


def test_description_is_optional(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "OTHER", "event_date": PAST.isoformat()}
    )

    assert response.status_code == 201
    assert response.json()["description"] == ""


def test_create_syncs_status_in_same_request(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    auth_api(profile.user).post(
        URL, {"event_type": "JOINING_LETTER", "event_date": PAST.isoformat()}
    )

    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINING_LETTER_RECEIVED


def test_backfilled_milestone_multi_hops(make_user, make_profile, auth_api):
    """REGISTERED + SELECTION walks the chain (T4.3's walk), not a single hop."""
    profile = make_profile(user=make_user())

    auth_api(profile.user).post(URL, {"event_type": "SELECTION", "event_date": PAST.isoformat()})

    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.SELECTED


def test_blocked_chain_returns_400_and_persists_nothing(make_user, make_profile, auth_api):
    """D1's own example over HTTP: JOINED already reached, INTERVIEW arrives late."""
    profile = make_profile(user=make_user(), current_status=CandidateProfile.Status.JOINED)

    response = auth_api(profile.user).post(
        URL, {"event_type": "INTERVIEW", "event_date": PAST.isoformat()}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "status_terminal"
    assert TimelineEvent.objects.count() == 0  # rollback proof (04 §85)


def test_other_event_leaves_status_untouched(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "OTHER", "event_date": PAST.isoformat()}
    )

    assert response.status_code == 201
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.REGISTERED
    assert TimelineEvent.objects.count() == 1


def test_unknown_event_type_is_rejected(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "BOGUS", "event_date": PAST.isoformat()}
    )

    assert response.status_code == 400
    assert "event_type" in response.json()
    assert TimelineEvent.objects.count() == 0


def test_is_verified_cannot_be_self_asserted(make_user, make_profile, auth_api):
    """06 §4.4 vertical escalation: verification is a moderation flag (Phase 8)."""
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "INTERVIEW", "event_date": PAST.isoformat(), "is_verified": True}
    )

    assert response.status_code == 201
    assert response.json()["is_verified"] is False
    assert TimelineEvent.objects.get().is_verified is False


def test_body_cannot_retarget_ownership(make_user, make_profile, auth_api):
    """06 §4.5: `candidate`/`user` in the body are not serializer fields."""
    mine = make_profile(user=make_user())
    theirs = make_profile(user=make_user())

    response = auth_api(mine.user).post(
        URL,
        {
            "event_type": "INTERVIEW",
            "event_date": PAST.isoformat(),
            "candidate": str(theirs.id),
            "user": str(theirs.user_id),
        },
    )

    assert response.status_code == 201
    assert TimelineEvent.objects.get().candidate_id == mine.id
    assert theirs.timeline_events.count() == 0


def test_future_date_at_horizon_is_allowed(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())
    edge = TODAY + timedelta(days=730)

    response = auth_api(profile.user).post(
        URL, {"event_type": "JOINING_DATE", "event_date": edge.isoformat()}
    )

    assert response.status_code == 201


def test_future_date_past_horizon_is_rejected(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())
    too_far = TODAY + timedelta(days=731)

    response = auth_api(profile.user).post(
        URL, {"event_type": "JOINING_DATE", "event_date": too_far.isoformat()}
    )

    assert response.status_code == 400
    assert "event_date" in response.json()


def test_absurd_past_date_is_rejected(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "INTERVIEW", "event_date": "1999-12-31"}
    )

    assert response.status_code == 400
    assert "event_date" in response.json()


def test_joining_letter_cannot_be_dated_in_the_future(make_user, make_profile, auth_api):
    """D3 carve-out: a letter is issued, not planned."""
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL,
        {"event_type": "JOINING_LETTER", "event_date": (TODAY + timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 400
    assert "event_date" in response.json()
    assert TimelineEvent.objects.count() == 0


def test_joining_letter_today_is_allowed(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "JOINING_LETTER", "event_date": TODAY.isoformat()}
    )

    assert response.status_code == 201


def test_joining_date_may_be_in_the_future(make_user, make_profile, auth_api):
    """D3 explicitly keeps upcoming joining dates recordable."""
    profile = make_profile(user=make_user())
    ahead = TODAY + timedelta(days=180)

    response = auth_api(profile.user).post(
        URL, {"event_type": "JOINING_DATE", "event_date": ahead.isoformat()}
    )

    assert response.status_code == 201
    profile.refresh_from_db()
    assert profile.current_status == CandidateProfile.Status.JOINING_DATE_RECEIVED


def test_invalid_date_format_is_rejected(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(
        URL, {"event_type": "INTERVIEW", "event_date": "not-a-date"}
    )

    assert response.status_code == 400
    assert "event_date" in response.json()


def test_profile_less_user_gets_profile_not_found(make_user, auth_api):
    response = auth_api(make_user()).post(
        URL, {"event_type": "INTERVIEW", "event_date": PAST.isoformat()}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"


def test_anonymous_is_rejected(api):
    assert api.post(URL, {"event_type": "INTERVIEW"}).status_code == 401
