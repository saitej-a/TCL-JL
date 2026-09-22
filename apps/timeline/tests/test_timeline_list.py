"""GET /api/v1/timeline/ — T4.4 list, scoping, pagination, filters (04 §9, §24.1).

Scoping is the IDOR layer that matters most here: a list endpoint that forgets to
filter would leak every candidate's private milestones at scale, which is why the
"other user's events are absent" cases below are the point of the file.
"""

from datetime import date, timedelta

import pytest

from apps.timeline.models import TimelineEvent

pytestmark = pytest.mark.django_db

URL = "/api/v1/timeline/"

RESULT_KEYS = {"id", "event_type", "event_date", "description", "is_verified", "created_at"}


def test_list_shape_matches_spec(make_user, make_profile, make_event, auth_api):
    user = make_user()
    profile = make_profile(user=user)
    make_event(profile, event_type="INTERVIEW", event_date=date(2026, 4, 23))
    make_event(profile, event_type="OFFER_LETTER", event_date=date(2026, 5, 5))

    response = auth_api(user).get(URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 2
    assert body["next"] is None and body["previous"] is None
    assert set(body["results"][0]) == RESULT_KEYS


def test_ordering_is_newest_first(make_user, make_profile, make_event, auth_api):
    profile = make_profile(user=make_user())
    for day in (date(2026, 1, 1), date(2026, 3, 1), date(2026, 2, 1)):
        make_event(profile, event_date=day)

    results = auth_api(profile.user).get(URL).json()["results"]

    assert [r["event_date"] for r in results] == ["2026-03-01", "2026-02-01", "2026-01-01"]


def test_same_date_falls_back_to_newest_created(make_user, make_profile, make_event, auth_api):
    """Tiebreak: two milestones on one day render most-recently-recorded first."""
    profile = make_profile(user=make_user())
    first = make_event(profile, event_date=date(2026, 6, 1), description="recorded first")
    second = make_event(profile, event_date=date(2026, 6, 1), description="recorded second")

    results = auth_api(profile.user).get(URL).json()["results"]

    assert [r["id"] for r in results] == [str(second.id), str(first.id)]


def test_other_candidates_events_are_absent(make_user, make_profile, make_event, auth_api):
    mine = make_profile(user=make_user())
    theirs = make_profile(user=make_user())
    make_event(mine)
    for _ in range(30):
        make_event(theirs)

    body = auth_api(mine.user).get(URL).json()

    assert body["count"] == 1
    assert [r["id"] for r in body["results"]] == [str(mine.timeline_events.first().id)]


def test_empty_timeline_returns_empty_page(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    body = auth_api(profile.user).get(URL).json()

    assert body == {"count": 0, "next": None, "previous": None, "results": []}


def test_filter_by_event_type(make_user, make_profile, make_event, auth_api):
    profile = make_profile(user=make_user())
    make_event(profile, event_type="INTERVIEW")
    make_event(profile, event_type="JOINING_LETTER", event_date=date(2026, 9, 1))

    body = auth_api(profile.user).get(f"{URL}?event_type=JOINING_LETTER").json()

    assert body["count"] == 1
    assert body["results"][0]["event_type"] == "JOINING_LETTER"


def test_unknown_filter_value_is_rejected(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).get(f"{URL}?event_type=BOGUS")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_event_type"


def test_arbitrary_page_size_is_ignored(make_user, make_profile, make_event, auth_api):
    """04 §9: never honour a client-supplied page size. The global paginator has
    no `page_size_query_param`, so `?page_size=999` cannot widen the page."""
    profile = make_profile(user=make_user())
    for _ in range(25):
        make_event(profile)

    body = auth_api(profile.user).get(f"{URL}?page_size=999").json()

    assert len(body["results"]) == 20
    assert body["count"] == 25


def test_second_page(make_user, make_profile, make_event, auth_api):
    profile = make_profile(user=make_user())
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(25)]
    for day in days:
        make_event(profile, event_date=day)
    client = auth_api(profile.user)

    first = client.get(URL).json()
    second = client.get(f"{URL}?page=2").json()

    assert first["next"] is not None and first["previous"] is None
    assert len(second["results"]) == 5
    assert second["previous"] is not None and second["next"] is None
    # The oldest five, still rendered newest-first (ordering is global, not per page).
    assert [r["event_date"] for r in second["results"]] == [
        d.isoformat() for d in sorted(days, reverse=True)[-5:]
    ]


def test_anonymous_is_rejected(api):
    assert api.get(URL).status_code == 401


def test_unverified_is_rejected(make_unverified_user, api):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=make_unverified_user)

    assert client.get(URL).status_code == 403


def test_inactive_is_rejected(make_inactive_user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=make_inactive_user)

    assert client.get(URL).status_code == 403


def test_profile_less_user_gets_profile_not_found(make_user, auth_api):
    """No `CandidateProfile` ⇒ 3.2's envelope, not a silently empty timeline."""
    response = auth_api(make_user()).get(URL)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"


def test_list_does_not_expose_other_candidates_via_filter(
    make_user, make_profile, make_event, auth_api
):
    """The `?event_type=` filter must narrow *within* the owner's rows, never
    widen the scope to the whole table."""
    mine = make_profile(user=make_user())
    theirs = make_profile(user=make_user())
    make_event(theirs, event_type="JOINING_LETTER")
    make_event(mine, event_type="INTERVIEW")

    body = auth_api(mine.user).get(f"{URL}?event_type=JOINING_LETTER").json()

    assert body["count"] == 0
    assert TimelineEvent.objects.filter(event_type="JOINING_LETTER").count() == 1
