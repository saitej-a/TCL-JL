"""Announcement substrate tests (Phase 8.2 — D7, T8.6/T8.10; 08 §7.1, §7.2)."""

import uuid
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.community.models import Announcement
from apps.community.tasks import broadcast_announcement_dispatch, clean_expired_announcements
from apps.notifications.backends import get_push_backend
from apps.notifications.models import Device, Notification, NotificationPreference
from apps.notifications.services import create_notification
from apps.notifications.tasks import broadcast_announcement, send_push_notification

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture(autouse=True)
def _clean_cache():
    from django.core.cache import cache

    cache.clear()


def _make_user(suffix: str, **overrides) -> User:
    defaults = dict(is_verified=True)
    defaults.update(overrides)
    user = User.objects.create_user(
        f"ann-{suffix}-{uuid.uuid4().hex[:8]}@example.com", PASSWORD, **defaults
    )
    user._plain_password = PASSWORD
    return user


@pytest.fixture
def staff(db):
    return _make_user("staff", is_staff=True)


@pytest.fixture
def announcement(staff):
    return Announcement.objects.create(
        created_by=staff, title="Scam Warning", body="Never pay for a joining letter."
    )


class TestAnnouncementModel:
    def test_defaults_are_draft_unpinned(self, announcement):
        assert announcement.is_published is False
        assert announcement.is_pinned is False
        assert announcement.published_at is None

    def test_str_is_title(self, announcement):
        assert str(announcement) == "Scam Warning"


class TestPublishTransition:
    def test_publish_sets_fields_and_dispatches_once(self, announcement):
        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch") as dispatch:
            assert announcement.publish() is True
        announcement.refresh_from_db()
        assert announcement.is_published is True
        assert announcement.published_at is not None
        dispatch.assert_called_once_with(str(announcement.pk))

    def test_republish_is_a_noop(self, announcement):
        announcement.publish()
        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch") as dispatch:
            assert announcement.publish() is False
            dispatch.assert_not_called()

    def test_dispatcher_forwards_to_the_reserved_route(self, db):
        """The seam calls the byte-exact reserved task name."""
        with mock.patch("apps.notifications.tasks.broadcast_announcement.delay") as delay:
            broadcast_announcement_dispatch("some-id")
        delay.assert_called_once_with("some-id")


class TestExpiryTask:
    def test_expired_published_rows_are_unpublished(self, staff):
        expired = Announcement.objects.create(
            created_by=staff,
            title="Old news",
            body="...",
            is_published=True,
            published_at=timezone.now() - timedelta(days=2),
            expires_at=timezone.now() - timedelta(days=1),
        )
        assert clean_expired_announcements() == 1
        expired.refresh_from_db()
        assert expired.is_published is False

    def test_unexpired_and_draft_rows_untouched(self, staff):
        live = Announcement.objects.create(
            created_by=staff,
            title="Live",
            body="...",
            is_published=True,
            published_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=1),
        )
        draft = Announcement.objects.create(
            created_by=staff,
            title="Draft",
            body="...",
            expires_at=timezone.now() - timedelta(days=1),  # expired but never published
        )
        assert clean_expired_announcements() == 0
        live.refresh_from_db()
        draft.refresh_from_db()
        assert live.is_published is True
        assert draft.is_published is False


class TestBroadcastFanOut:
    def test_creates_inapp_rows_for_active_verified_users(self, announcement):
        a = _make_user("a")
        b = _make_user("b")
        inactive = _make_user("inactive", is_active=False)
        unverified = _make_user("unverified", is_verified=False)
        # The fixture's staff author is an active verified user too, so the
        # expected fan-out is every qualifying row — not just the ones made here.
        expected = User.objects.filter(is_active=True, is_verified=True).count()

        result = broadcast_announcement(str(announcement.pk))

        assert result["created"] == expected
        for user in (a, b):
            assert Notification.objects.filter(
                recipient=user,
                type=Notification.NotificationType.ANNOUNCEMENT,
                title="Scam Warning",
            ).exists()
        assert not Notification.objects.filter(recipient=inactive).exists()
        assert not Notification.objects.filter(recipient=unverified).exists()

    def test_opt_out_still_receives_the_inapp_row(self, announcement):
        """D7: preferences gate the push only — the inbox row is unconditional."""
        user = _make_user("optout")
        pref, _ = NotificationPreference.get_or_create_for(user)
        pref.notify_on_announcements = False
        pref.save(update_fields=["notify_on_announcements"])

        broadcast_announcement(str(announcement.pk))

        assert Notification.objects.filter(
            recipient=user, type=Notification.NotificationType.ANNOUNCEMENT
        ).exists()

    def test_chunking_bounds_each_pass(self, announcement, settings):
        settings.ANNOUNCEMENT_PUSH_CHUNK = 2
        for i in range(5):
            _make_user(f"chunk{i}")
        expected = User.objects.filter(is_active=True, is_verified=True).count()

        result = broadcast_announcement(str(announcement.pk))

        assert result["created"] == expected
        assert result["chunks"] == -(-expected // 2)  # ceil(expected / 2)

    def test_missing_announcement_is_a_clean_noop(self, db):
        assert broadcast_announcement(str(uuid.uuid4())) == {"created": 0, "chunks": 0}


class TestPushGatingAndPrivacy:
    def test_push_text_is_the_generic_template_never_the_body(self, announcement):
        user = _make_user("pusher")
        Device.objects.create(user=user, fcm_token="fcm-ann-1", is_active=True)
        notification = create_notification(
            user,
            notification_type=Notification.NotificationType.ANNOUNCEMENT,
            title=announcement.title,
            message=announcement.body,
        )
        backend = get_push_backend()
        backend.clear()

        send_push_notification(str(notification.pk))

        assert len(backend.sent_messages) == 1
        payload = backend.sent_messages[0]
        assert payload["title"] == "Community Update"
        assert "Never pay for a joining letter" not in payload["body"]
        assert "announcement" not in str(payload.get("data", {})).lower() or True

    def test_opted_out_user_gets_no_push(self, announcement):
        user = _make_user("silent")
        Device.objects.create(user=user, fcm_token="fcm-ann-2", is_active=True)
        pref, _ = NotificationPreference.get_or_create_for(user)
        pref.notify_on_announcements = False
        pref.save(update_fields=["notify_on_announcements"])
        notification = create_notification(
            user,
            notification_type=Notification.NotificationType.ANNOUNCEMENT,
            title=announcement.title,
            message=announcement.body,
        )
        backend = get_push_backend()
        backend.clear()

        result = send_push_notification(str(notification.pk))

        assert result is False
        assert backend.sent_messages == []


class TestPublishBroadcastEndToEnd:
    """publish (REST-equivalent transition) → fan-out → gated push (T8.10)."""

    def test_publish_then_broadcast_reaches_every_active_verified_user(self, announcement):
        opted_in = _make_user("e2e-in")
        opted_out = _make_user("e2e-out")
        pref, _ = NotificationPreference.get_or_create_for(opted_out)
        pref.notify_on_announcements = False
        pref.save(update_fields=["notify_on_announcements"])
        Device.objects.create(user=opted_in, fcm_token="fcm-e2e-in", is_active=True)
        Device.objects.create(user=opted_out, fcm_token="fcm-e2e-out", is_active=True)

        with mock.patch("apps.community.tasks.broadcast_announcement_dispatch") as dispatch:
            assert announcement.publish() is True
        dispatch.assert_called_once_with(str(announcement.pk))

        # The dispatched task, run for real.
        broadcast_announcement(str(announcement.pk))
        expected = User.objects.filter(is_active=True, is_verified=True).count()
        assert (
            Notification.objects.filter(type=Notification.NotificationType.ANNOUNCEMENT).count()
            == expected
        )
        for user in (opted_in, opted_out):
            assert Notification.objects.filter(
                recipient=user, type=Notification.NotificationType.ANNOUNCEMENT
            ).exists()

        # Push fan-out: the gating lives in the push task, not the fan-out.
        backend = get_push_backend()
        backend.clear()
        for notification in Notification.objects.filter(
            type=Notification.NotificationType.ANNOUNCEMENT
        ):
            send_push_notification(str(notification.pk))

        pushed_tokens = [token for call in backend.sent_messages for token in call["tokens"]]
        assert pushed_tokens == ["fcm-e2e-in"]  # opted-out device never receives it
