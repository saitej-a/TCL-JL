"""Admin triage action tests (Phase 8.2 — MOD-05, T8.9; 08 §9.1, §14.1)."""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import RequestFactory

from apps.accounts.admin import UserAdmin
from apps.accounts.models import User
from apps.community.models import Post
from apps.moderation.admin import ReportAdmin
from apps.moderation.models import Report
from apps.moderation.services import create_report
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        "admin.mod@example.com", PASSWORD, is_verified=True, is_staff=True
    )


@pytest.fixture
def report_admin():
    return ReportAdmin(Report, AdminSite())


@pytest.fixture
def user_admin():
    return UserAdmin(User, AdminSite())


def _request(user):
    """A RequestFactory request wired for admin actions (messages + user)."""
    request = RequestFactory().post("/admin/")
    request.user = user
    request.session = {}
    request._messages = CookieStorage(request)
    return request


def _messages(request) -> str:
    return " ".join(str(m.message) for m in request._messages)


def _second_staff() -> User:
    """A second staff account — the acting moderator differs from the target."""
    return User.objects.create_user(
        "second.mod@example.com", PASSWORD, is_verified=True, is_staff=True
    )


@pytest.fixture
def pending_reports(reporter, other_reporter, author, post, comment):
    """Three PENDING reports: two post-targeted, one comment-targeted."""
    return {
        "spam_post": create_report(reporter, post=post, reason="SPAM"),
        "scam_post": create_report(other_reporter, post=post, reason="SCAM"),
        "abuse_comment": create_report(
            User.objects.create_user("third@example.com", PASSWORD, is_verified=True),
            comment=comment,
            reason="HARASSMENT",
        ),
    }


class TestReportAdminConfig:
    def test_spec_columns_and_actions(self, report_admin):
        display = list(report_admin.list_display)
        assert display[:3] == ["id", "target_type", "reason"]
        assert "reviewed_by" in display
        assert set(report_admin.actions) >= {
            "dismiss_reports",
            "soft_delete_and_resolve",
            "lock_posts",
            "warn_users",
            "ban_users",
        }
        assert "status" in report_admin.list_filter
        assert "post__title" in report_admin.search_fields

    def test_target_type_display(self, report_admin, pending_reports):
        assert report_admin.target_type(pending_reports["scam_post"]) == "POST"
        assert report_admin.target_type(pending_reports["abuse_comment"]) == "COMMENT"


class TestDismissAction:
    def test_dismisses_pending_and_skips_terminal(
        self, report_admin, staff, pending_reports, post, comment
    ):
        request = _request(staff)
        queryset = Report.objects.all()
        report_admin.dismiss_reports(request, queryset)
        assert Report.objects.filter(status=Report.ReportStatus.DISMISSED).count() == 3
        for report in Report.objects.all():
            assert report.reviewed_by == staff
            assert report.reviewed_at is not None
        # Content untouched by a dismissal.
        post.refresh_from_db()
        comment.refresh_from_db()
        assert (post.is_deleted, post.is_locked) == (False, False)
        assert comment.is_deleted is False

        # Second pass: everything is terminal → skipped, not re-reviewed.
        request2 = _request(staff)
        report_admin.dismiss_reports(request2, Report.objects.all())
        assert "skipped 3 already-reviewed" in _messages(request2)


class TestSoftDeleteAndResolve:
    def test_tombstones_targets_and_notifies_authors(
        self, report_admin, staff, pending_reports, post, comment
    ):
        request = _request(staff)
        report_admin.soft_delete_and_resolve(request, Report.objects.all())

        post.refresh_from_db()
        comment.refresh_from_db()
        assert post.is_deleted is True
        assert post.body  # originals retained (§5 audit)
        assert comment.is_deleted is True
        assert Report.objects.filter(status=Report.ReportStatus.RESOLVED).count() == 3
        # Both content authors warned once each (post author == comment author fixture).
        assert (
            Notification.objects.filter(type=Notification.NotificationType.MODERATION).count() >= 1
        )
        assert "Removed content and resolved 3 report(s)" in _messages(request)


class TestLockWarnBanActions:
    def test_lock_posts_locks_and_reports_comment_failure(
        self, report_admin, staff, pending_reports, post, comment
    ):
        request = _request(staff)
        report_admin.lock_posts(request, Report.objects.all())
        post.refresh_from_db()
        assert post.is_locked is True
        comment_report = pending_reports["abuse_comment"]
        comment_report.refresh_from_db()
        assert comment_report.status == Report.ReportStatus.PENDING  # refused, not resolved
        message = _messages(request)
        assert "Locked threads for 2 report(s)" in message
        assert "failed:" in message

    def test_warn_users_notifies_without_touching_content(
        self, report_admin, staff, pending_reports, post
    ):
        request = _request(staff)
        report_admin.warn_users(request, Report.objects.all())
        post.refresh_from_db()
        assert (post.is_deleted, post.is_locked) == (False, False)
        assert (
            Notification.objects.filter(type=Notification.NotificationType.MODERATION).count() == 3
        )
        assert Report.objects.filter(status=Report.ReportStatus.RESOLVED).count() == 3

    def test_ban_users_bans_authors_and_refuses_staff(
        self, report_admin, staff, pending_reports, author
    ):
        request = _request(staff)
        report_admin.ban_users(request, Report.objects.all())
        author.refresh_from_db()
        assert author.is_active is False
        assert author.banned_until is None  # permanent

        # A report against a staff member's own content is refused, not applied.
        staff_post = Post.objects.create(
            author=staff, title="Moderator note", body="Internal", category="GENERAL"
        )
        staff_report = create_report(
            User.objects.create_user("fourth@example.com", PASSWORD, is_verified=True),
            post=staff_post,
            reason="OTHER",
        )
        request2 = _request(_second_staff())
        report_admin.ban_users(request2, Report.objects.filter(pk=staff_report.pk))
        staff.refresh_from_db()
        assert staff.is_active is True
        staff_report.refresh_from_db()
        assert staff_report.status == Report.ReportStatus.PENDING
        assert "refused" in _messages(request2) or "failed:" in _messages(request2)


class TestUserAdminActions:
    def test_list_display_shows_banned_until(self, user_admin):
        assert "banned_until" in user_admin.list_display

    def test_ban_selected_users_uses_service(self, user_admin, staff, author):
        request = _request(staff)
        user_admin.ban_selected_users(request, User.objects.filter(pk=author.pk))
        author.refresh_from_db()
        assert author.is_active is False
        assert "Suspended 1 account(s)" in _messages(request)

    def test_ban_action_refuses_staff_target(self, user_admin, staff):
        other = _second_staff()
        request = _request(staff)
        user_admin.ban_selected_users(request, User.objects.filter(pk=other.pk))
        other.refresh_from_db()
        assert other.is_active is True
        assert "refused" in _messages(request)

    def test_unban_action_reactivates(self, user_admin, staff, author):
        author.is_active = False
        author.banned_until = None
        author.save(update_fields=["is_active", "banned_until"])

        request = _request(staff)
        user_admin.unban_selected_users(request, User.objects.filter(pk=author.pk))
        author.refresh_from_db()
        assert author.is_active is True
        assert "Reinstated 1 account(s)" in _messages(request)
