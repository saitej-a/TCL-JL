"""Triage REST API tests (Phase 8.2 — D4/D5/D6; 04 §67–§70, 08 §4.1, §9.2)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.moderation.models import Report

pytestmark = pytest.mark.django_db

QUEUE_URL = "/api/v1/moderation/reports/"
REVIEW_URL = "/api/v1/moderation/reports/{id}/review/"
BAN_URL = "/api/v1/moderation/users/{id}/ban/"
UNBAN_URL = "/api/v1/moderation/users/{id}/unban/"
PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        "queue.mod@example.com", PASSWORD, is_verified=True, is_staff=True
    )


@pytest.fixture
def staff_client(db, staff):
    """Its own client — sharing the `api` fixture would let a test that
    authenticates `api` as a candidate also re-authenticate the staff client."""
    client = APIClient()
    client.force_authenticate(user=staff)
    return client


def _report(reporter, target_post=None, target_comment=None, reason="SPAM", **kwargs):
    from apps.moderation.services import create_report

    return create_report(
        reporter,
        post=target_post,
        comment=target_comment,
        reason=reason,
        **kwargs,
    )


class TestModerationQueueAccess:
    def test_regular_candidate_gets_403(self, api, reporter, post, db):
        api.force_authenticate(user=reporter)
        response = api.get(QUEUE_URL)
        assert response.status_code == 403

    def test_staff_lists_pending_reports(self, staff_client, reporter, post):
        _report(reporter, target_post=post, reason="SCAM")
        response = staff_client.get(QUEUE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        row = body["results"][0]
        assert set(row) == {
            "id",
            "reason",
            "status",
            "post_id",
            "comment_id",
            "description",
            "created_at",
        }
        assert row["reason"] == "SCAM"
        assert row["status"] == "PENDING"
        assert str(post.id) == row["post_id"]

    def test_queue_never_leaks_moderator_fields(self, staff_client, reporter, post):
        report = _report(reporter, target_post=post)
        from apps.moderation.services import resolve_report

        resolve_report(
            report,
            User.objects.create_user("rev@example.com", PASSWORD, is_staff=True, is_verified=True),
            action="DISMISS",
            moderator_notes="internal note",
        )
        report.refresh_from_db()
        response = staff_client.get(QUEUE_URL + "?status=DISMISSED")
        assert response.status_code == 200
        row = response.json()["results"][0]
        assert "moderator_notes" not in row
        assert "reviewed_by" not in row
        assert "reviewer" not in row

    def test_invalid_status_filter_is_400(self, staff_client, reporter, post):
        response = staff_client.get(QUEUE_URL + "?status=BOGUS")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_filter"

    def test_default_filter_is_pending(self, staff_client, reporter, post, comment):
        report = _report(reporter, target_post=post)
        from apps.moderation.services import resolve_report

        resolve_report(report, _any_staff(), action="DISMISS")
        _report(reporter, target_comment=comment)  # stays PENDING
        body = staff_client.get(QUEUE_URL).json()
        assert body["count"] == 1
        assert body["results"][0]["status"] == "PENDING"


def _any_staff():
    return User.objects.get(email="queue.mod@example.com")


class TestQueueOrdering:
    def test_severity_order_scam_first(self, staff_client, reporter, post, comment, other_reporter):
        scam = _report(reporter, target_post=post, reason="SCAM")
        other = _report(other_reporter, target_comment=comment, reason="OTHER")
        assert scam.created_at <= other.created_at  # sanity on fixture ordering

        body = staff_client.get(QUEUE_URL).json()
        reasons = [row["reason"] for row in body["results"]]
        assert reasons == ["SCAM", "OTHER"]

    def test_same_severity_newest_first(
        self, staff_client, reporter, post, comment, other_reporter
    ):
        spam_post = _report(reporter, target_post=post, reason="SPAM")
        spam_comment = _report(other_reporter, target_comment=comment, reason="SPAM")

        body = staff_client.get(QUEUE_URL).json()
        ids = [row["id"] for row in body["results"]]
        assert ids == [str(spam_comment.id), str(spam_post.id)]  # later-created first


class TestReviewEndpoint:
    def test_unknown_report_is_404(self, staff_client):
        response = staff_client.post(
            REVIEW_URL.format(id="not-a-uuid"), {"action": "DISMISS"}, format="json"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "report_not_found"

    def test_dismiss_resolves_as_dismissed(self, staff_client, reporter, post):
        report = _report(reporter, target_post=post)
        response = staff_client.post(
            REVIEW_URL.format(id=report.id), {"action": "DISMISS"}, format="json"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["action"] == "DISMISS"
        assert body["status"] == "DISMISSED"
        report.refresh_from_db()
        assert report.reviewed_by == _any_staff()
        assert report.reviewed_at is not None

    def test_remove_content_tombstones_and_notifies(self, staff_client, reporter, post, author):
        from apps.notifications.models import Notification

        report = _report(reporter, target_post=post)
        response = staff_client.post(
            REVIEW_URL.format(id=report.id), {"action": "REMOVE_CONTENT"}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "RESOLVED"
        post.refresh_from_db()
        assert post.is_deleted is True
        assert Notification.objects.filter(
            recipient=author, type=Notification.NotificationType.MODERATION
        ).exists()

    def test_lock_post_locks_and_comment_target_is_400(self, staff_client, reporter, post, comment):
        post_report = _report(reporter, target_post=post)
        response = staff_client.post(
            REVIEW_URL.format(id=post_report.id), {"action": "LOCK_POST"}, format="json"
        )
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.is_locked is True

        comment_report = _report(reporter, target_comment=comment)
        response = staff_client.post(
            REVIEW_URL.format(id=comment_report.id), {"action": "LOCK_POST"}, format="json"
        )
        assert response.status_code == 400
        comment_report.refresh_from_db()
        assert comment_report.status == "PENDING"  # rolled back

    def test_warn_user_notifies_without_touching_content(
        self, staff_client, reporter, post, author
    ):
        from apps.notifications.models import Notification

        report = _report(reporter, target_post=post)
        response = staff_client.post(
            REVIEW_URL.format(id=report.id), {"action": "WARN_USER"}, format="json"
        )
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.is_deleted is False
        assert post.is_locked is False
        assert Notification.objects.filter(
            recipient=author, type=Notification.NotificationType.MODERATION
        ).exists()

    def test_ban_user_resolves_and_schedules_enforcement(
        self, staff_client, reporter, post, author, target_device
    ):
        report = _report(reporter, target_post=post)
        response = staff_client.post(
            REVIEW_URL.format(id=report.id),
            {"action": "BAN_USER", "duration_days": 7},
            format="json",
        )
        assert response.status_code == 202
        body = response.json()
        assert body["action"] == "BAN_USER"
        assert body["status"] == "RESOLVED"
        author.refresh_from_db()
        assert author.is_active is False
        assert author.banned_until is not None
        # Severing is async (D1) — device still active until the task runs.
        assert target_device.is_active is True

    def test_unknown_action_is_400(self, staff_client, reporter, post):
        report = _report(reporter, target_post=post)
        response = staff_client.post(
            REVIEW_URL.format(id=report.id), {"action": "NUKE"}, format="json"
        )
        assert response.status_code == 400


class TestBanUnbanEndpoints:
    def test_regular_user_cannot_ban(self, api, reporter, author):
        api.force_authenticate(user=reporter)
        response = api.post(BAN_URL.format(id=author.id), {"reason": "SCAM"}, format="json")
        assert response.status_code == 403

    def test_staff_ban_is_202_and_severs(self, staff_client, author, target_device):
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(author)
        token.outstand()

        response = staff_client.post(
            BAN_URL.format(id=author.id), {"reason": "SCAM"}, format="json"
        )
        assert response.status_code == 202
        body = response.json()
        assert body["is_active"] is False
        assert body["banned_until"] is None
        assert "email" not in body

        author.refresh_from_db()
        assert author.is_active is False
        assert target_device.is_active is True  # async — before task run

    def test_staff_temporary_ban_sets_banned_until(self, staff_client, author):
        response = staff_client.post(
            BAN_URL.format(id=author.id),
            {"reason": "HARASSMENT", "duration_days": 7},
            format="json",
        )
        assert response.status_code == 202
        author.refresh_from_db()
        assert author.banned_until is not None

    def test_unban_reactivates(self, staff_client, author):
        staff_client.post(BAN_URL.format(id=author.id), {"reason": "SCAM"}, format="json")
        response = staff_client.post(UNBAN_URL.format(id=author.id), format="json")
        assert response.status_code == 200
        author.refresh_from_db()
        assert author.is_active is True

    def test_cannot_ban_staff(self, staff_client, staff):
        response = staff_client.post(BAN_URL.format(id=staff.id), {"reason": "SCAM"}, format="json")
        assert response.status_code == 400
        staff.refresh_from_db()
        assert staff.is_active is True

    def test_unknown_user_is_404(self, staff_client):
        response = staff_client.post(BAN_URL.format(id="nope"), {"reason": "SCAM"}, format="json")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "user_not_found"


# --- Task 6: end-to-end integration + 04 §107's required names --------------------


class TestSpecRequiredNames:
    """04 §107's moderation test inventory, by name."""

    def test_admin_can_review_report(self, staff_client, reporter, post):
        report = _report(reporter, target_post=post, reason="SPAM")
        response = staff_client.post(
            REVIEW_URL.format(id=report.id), {"action": "DISMISS"}, format="json"
        )
        assert response.status_code == 200
        report.refresh_from_db()
        assert report.status == Report.ReportStatus.DISMISSED
        assert report.reviewed_by == _any_staff()

    def test_regular_user_cannot_review_report(self, api, reporter, author, post):
        report = _report(reporter, target_post=post)
        api.force_authenticate(user=author)  # a candidate who is not the reporter
        response = api.post(REVIEW_URL.format(id=report.id), {"action": "DISMISS"}, format="json")
        assert response.status_code == 403
        report.refresh_from_db()
        assert report.status == Report.ReportStatus.PENDING

    def test_remove_content(self, staff_client, reporter, post, author):
        report = _report(reporter, target_post=post, reason="SCAM")
        response = staff_client.post(
            REVIEW_URL.format(id=report.id), {"action": "REMOVE_CONTENT"}, format="json"
        )
        assert response.status_code == 200
        post.refresh_from_db()
        assert post.is_deleted is True


class TestTriageLoopEndToEnd:
    """candidate reports → staff lists → review → tombstone + notify → re-report."""

    def test_report_to_removal_loop(self, api, staff_client, reporter, author, post):
        from apps.notifications.models import Notification

        api.force_authenticate(user=reporter)
        created = api.post(
            "/api/v1/reports/", {"post_id": str(post.id), "reason": "SCAM"}, format="json"
        )
        assert created.status_code == 201

        queue = staff_client.get(QUEUE_URL).json()
        assert queue["count"] == 1
        assert queue["results"][0]["reason"] == "SCAM"
        report_id = queue["results"][0]["id"]

        reviewed = staff_client.post(
            REVIEW_URL.format(id=report_id), {"action": "REMOVE_CONTENT"}, format="json"
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "RESOLVED"

        post.refresh_from_db()
        assert post.is_deleted is True
        assert Notification.objects.filter(
            recipient=author, type=Notification.NotificationType.MODERATION
        ).exists()

        # 8.1's dedup is PENDING-only: the same reporter may report the tombstone
        # again (evidence-driven re-reporting is legitimate).
        again = api.post(
            "/api/v1/reports/", {"post_id": str(post.id), "reason": "SCAM"}, format="json"
        )
        assert again.status_code == 201


class TestBanLoopEndToEnd:
    """BAN_USER review → severing → suspended login → auto-reinstate (D1/D2/D3)."""

    LOGIN_URL = "/api/v1/auth/login/"

    def _login(self, email):
        from rest_framework.test import APIClient

        return APIClient().post(
            self.LOGIN_URL, {"email": email, "password": PASSWORD}, content_type="application/json"
        )

    def test_ban_severs_sessions_devices_and_login(self, staff_client, reporter, author, post):
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.tokens import RefreshToken

        from apps.moderation.tasks import sever_banned_user_sessions
        from apps.notifications.models import Device

        token = RefreshToken.for_user(author)
        token.outstand()
        raw_refresh = str(token)
        device = Device.objects.create(user=author, fcm_token="fcm-loop-1", is_active=True)

        assert self._login(author.email).status_code == 200  # can log in before the ban

        report = _report(reporter, target_post=post, reason="SCAM")
        response = staff_client.post(
            REVIEW_URL.format(id=report.id),
            {"action": "BAN_USER", "duration_days": 7},
            format="json",
        )
        assert response.status_code == 202

        author.refresh_from_db()
        assert author.is_active is False
        assert author.banned_until is not None  # temporary (D3)

        # The async half: severing.
        sever_banned_user_sessions(str(author.pk))
        with pytest.raises(TokenError):
            RefreshToken(raw_refresh)
        device.refresh_from_db()
        assert device.is_active is False
        assert self._login(author.email).status_code == 403  # ACCOUNT_SUSPENDED (§6.2)

        # Auto-reinstatement of the lapsed temporary ban.
        from datetime import timedelta

        from django.utils import timezone

        from apps.moderation.tasks import auto_reinstate_users

        author.banned_until = timezone.now() - timedelta(minutes=1)
        author.save(update_fields=["banned_until"])
        assert auto_reinstate_users() == 1
        author.refresh_from_db()
        assert author.is_active is True
        assert author.banned_until is None
        assert self._login(author.email).status_code == 200  # access restored

        # D2: severing stays one-way — the device is not revived by reinstatement.
        device.refresh_from_db()
        assert device.is_active is False

    def test_permanent_ban_survives_reinstatement_sweep(self, staff_client, author):
        from apps.moderation.services import ban_user
        from apps.moderation.tasks import auto_reinstate_users

        moderator = _any_staff()
        ban_user(moderator, author, reason="SCAM", duration_days=0)
        assert auto_reinstate_users() == 0
        author.refresh_from_db()
        assert author.is_active is False
        assert author.banned_until is None
