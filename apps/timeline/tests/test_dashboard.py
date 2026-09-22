"""GET /api/v1/dashboard/ — T4.8 aggregation (04 §28, §53, §65.20; 4.2 D1/D2).

Two properties carry the phase's product promise:

* **Community data is labeled and threshold-suppressed.** A raw count over a tiny
  cohort identifies people, and unlabeled community numbers read as official TCS
  information (04 §53, §65.20; 01 §1007).
* **The key contract is stable now** so the Phase 9.3 UI never churns: the
  notifications block is an explicit placeholder until Phase 6, not a missing key.
"""

from datetime import date, timedelta

import pytest
from django.test import override_settings

from apps.candidates.models import CandidateProfile
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

URL = "/api/v1/dashboard/"
S = CandidateProfile.Status


def _profile_with_status(make_user, make_profile, status):
    return make_profile(user=make_user(), current_status=status)


def test_top_level_shape_is_the_spec_contract(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    body = auth_api(profile.user).get(URL).json()

    assert set(body) == {"profile", "timeline", "community", "analytics"}
    assert set(body["profile"]) == {"completion_percentage", "current_status"}
    assert set(body["timeline"]) == {"latest_event"}
    assert set(body["community"]) == {"unread_notifications"}


def test_profile_block_mirrors_current_status(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user(), current_status=S.OFFER_RECEIVED)

    body = auth_api(profile.user).get(URL).json()

    assert body["profile"]["current_status"] == S.OFFER_RECEIVED
    assert isinstance(body["profile"]["completion_percentage"], int)


def test_latest_event_is_null_without_events(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    assert auth_api(profile.user).get(URL).json()["timeline"]["latest_event"] is None


def test_latest_event_is_newest_by_date_not_creation_order(
    make_user, make_profile, make_event, auth_api
):
    profile = make_profile(user=make_user())
    make_event(profile, event_type="INTERVIEW", event_date=date(2026, 9, 20))  # created first
    make_event(profile, event_type="OFFER_LETTER", event_date=date(2026, 3, 1))  # created later

    latest = auth_api(profile.user).get(URL).json()["timeline"]["latest_event"]

    assert latest == {"event_type": "INTERVIEW", "event_date": "2026-09-20"}


def test_latest_event_carries_no_private_notes(make_user, make_profile, make_event, auth_api):
    """Exactly 04 §28's two keys: descriptions are the owner's private notes and
    belong only in timeline responses (04 §744's spirit)."""
    profile = make_profile(user=make_user())
    make_event(profile, description="Personal note I only want on my timeline page.")

    latest = auth_api(profile.user).get(URL).json()["timeline"]["latest_event"]

    assert set(latest) == {"event_type", "event_date"}


def test_unread_notifications_is_the_real_count(make_user, make_profile, auth_api):
    """4.2 D1 debt paid in 6.2: dashboard returns the live unread count."""
    user = make_user()
    profile = make_profile(user=user)
    client = auth_api(profile.user)

    # 0 initially
    assert client.get(URL).json()["community"]["unread_notifications"] == 0

    # 3 unread notifications
    for idx in range(3):
        Notification.objects.create(
            recipient=user,
            type=Notification.NotificationType.SYSTEM,
            title=f"Notification {idx}",
            message="Message content",
        )
    assert client.get(URL).json()["community"]["unread_notifications"] == 3

    # Mark all read -> drops to 0
    from django.utils import timezone

    Notification.objects.filter(recipient=user).update(is_read=True, read_at=timezone.now())
    assert client.get(URL).json()["community"]["unread_notifications"] == 0


def test_community_data_is_labeled(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    analytics = auth_api(profile.user).get(URL).json()["analytics"]

    assert analytics["data_source"] == "COMMUNITY_REPORTED"


def test_waiting_count_excludes_joined_withdrawn_and_registered(make_user, make_profile, auth_api):
    """Five profiles clears the default threshold of five, so the full block renders."""
    requester = _profile_with_status(make_user, make_profile, S.WAITING_FOR_JOINING_LETTER)
    _profile_with_status(make_user, make_profile, S.REGISTERED)
    _profile_with_status(make_user, make_profile, S.JOINED)
    _profile_with_status(make_user, make_profile, S.WITHDRAWN)
    _profile_with_status(make_user, make_profile, S.JOINING_DATE_RECEIVED)

    analytics = auth_api(requester.user).get(URL).json()["analytics"]

    assert analytics["suppressed"] is False
    assert analytics["community_waiting_count"] == 2  # WAITING_FOR_JOINING_LETTER + JOINING_DATE
    assert CandidateProfile.objects.count() == 5


def test_status_distribution_carries_every_status_key(make_user, make_profile, auth_api):
    requester = make_profile(user=make_user())
    for _ in range(4):
        make_profile(user=make_user())

    distribution = auth_api(requester.user).get(URL).json()["analytics"]["status_distribution"]

    assert set(distribution) == set(S.values)
    assert sum(distribution.values()) == CandidateProfile.objects.count()


def test_small_cohort_is_suppressed_without_counts(make_user, make_profile, auth_api):
    """04 §53: below the threshold the counts are omitted, not zeroed."""
    requester = make_profile(user=make_user())
    make_profile(user=make_user())

    analytics = auth_api(requester.user).get(URL).json()["analytics"]

    assert analytics["suppressed"] is True
    assert "Not enough community data" in analytics["message"]
    assert "community_waiting_count" not in analytics
    assert "status_distribution" not in analytics
    assert analytics["data_source"] == "COMMUNITY_REPORTED"


@override_settings(ANALYTICS_MIN_COHORT_SIZE=3)
def test_threshold_boundary_is_inclusive(make_user, make_profile, auth_api):
    """Exactly-at-threshold renders; one below suppresses (setting is tunable)."""
    requester = make_profile(user=make_user())
    make_profile(user=make_user())
    make_profile(user=make_user())

    analytics = auth_api(requester.user).get(URL).json()["analytics"]

    assert analytics["suppressed"] is False
    assert "community_waiting_count" in analytics


@override_settings(ANALYTICS_MIN_COHORT_SIZE=3)
def test_one_below_threshold_suppresses(make_user, make_profile, auth_api):
    requester = make_profile(user=make_user())
    make_profile(user=make_user())

    analytics = auth_api(requester.user).get(URL).json()["analytics"]

    assert analytics["suppressed"] is True


def test_anonymous_is_rejected(api):
    assert api.get(URL).status_code == 401


def test_unverified_is_rejected(make_unverified_user):
    """Gating happens before profile resolution, so no profile is needed here."""
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=make_unverified_user)

    assert client.get(URL).status_code == 403


def test_profile_less_user_gets_profile_not_found(make_user, auth_api):
    response = auth_api(make_user()).get(URL)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"


def test_post_is_not_allowed(make_user, make_profile, auth_api):
    profile = make_profile(user=make_user())

    response = auth_api(profile.user).post(URL, {})

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_completion_reflects_recorded_milestones(make_user, make_profile, make_event, auth_api):
    """The dashboard's meter responds to the timeline, not just profile fields."""
    profile = make_profile(user=make_user(), current_status=S.JOINED)
    before = auth_api(profile.user).get(URL).json()["profile"]["completion_percentage"]
    make_event(profile, event_type="JOINED", event_date=date(2026, 9, 18))

    after = auth_api(profile.user).get(URL).json()["profile"]["completion_percentage"]

    assert after > before


def test_dashboard_uses_recent_dates_within_horizon(make_user, make_profile, make_event, auth_api):
    """Sanity check that future-dated milestones (allowed by D3) still surface."""
    profile = make_profile(user=make_user())
    ahead = date.today() + timedelta(days=90)
    make_event(profile, event_type="JOINING_DATE", event_date=ahead)

    latest = auth_api(profile.user).get(URL).json()["timeline"]["latest_event"]

    assert latest["event_date"] == ahead.isoformat()
