"""Tests for Celery push notification task (Phase 6.2 — 07 §5, §8, §12, D3, D5, D14)."""

from __future__ import annotations

import uuid

from django.core.cache import cache

from apps.notifications.backends import RecordingPushBackend, get_push_backend
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.tasks import prune_stale_devices, send_push_notification


def test_task_names_match_celery_task_routes():
    """Task names must exactly match keys in CELERY_TASK_ROUTES (base.py:225)."""
    assert send_push_notification.name == "notifications.tasks.send_push_notification"
    assert prune_stale_devices.name == "notifications.tasks.prune_stale_devices"


def test_task_discards_if_notification_does_not_exist():
    """Non-existent notification ID logs warning and returns False without failing."""
    result = send_push_notification.apply(args=[str(uuid.uuid4())]).get()
    assert result is False


def test_task_skipped_when_push_globally_disabled(make_user, make_device):
    """push_enabled=False short-circuits before devices or debounce (D14)."""
    user = make_user()
    make_device(user=user, fcm_token="token_123")
    pref, _ = NotificationPreference.get_or_create_for(user)
    pref.push_enabled = False
    pref.save()

    notif = Notification.objects.create(
        recipient=user,
        type=Notification.NotificationType.COMMENT,
        title="In-app title",
        message="In-app message",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    result = send_push_notification.apply(args=[str(notif.id)]).get()
    assert result is False

    if isinstance(backend, RecordingPushBackend):
        assert len(backend.sent_messages) == 0


def test_task_skipped_when_category_flag_disabled(make_user, make_post, make_device):
    """Category-level preference flags suppress push for that specific type (D14)."""
    user = make_user()
    post = make_post(author=user)
    make_device(user=user, fcm_token="token_123")

    pref, _ = NotificationPreference.get_or_create_for(user)
    pref.notify_on_comment = False
    pref.save()

    notif = Notification.objects.create(
        recipient=user,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="Comment title",
        message="Comment message",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    result = send_push_notification.apply(args=[str(notif.id)]).get()
    assert result is False

    if isinstance(backend, RecordingPushBackend):
        assert len(backend.sent_messages) == 0


def test_task_allowed_for_system_and_moderation_when_push_enabled(make_user, make_device):
    """SYSTEM and MODERATION are operational alerts gated only by push_enabled (D14)."""
    user = make_user()
    make_device(user=user, fcm_token="token_operational")

    pref, _ = NotificationPreference.get_or_create_for(user)
    pref.notify_on_comment = False
    pref.notify_on_reply = False
    pref.notify_on_vote_milestone = False
    pref.notify_on_announcements = False
    pref.notify_timeline_reminders = False
    pref.push_enabled = True
    pref.save()

    notif = Notification.objects.create(
        recipient=user,
        type=Notification.NotificationType.SYSTEM,
        title="System Notice",
        message="System alert body",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    result = send_push_notification.apply(args=[str(notif.id)]).get()
    assert result is True

    if isinstance(backend, RecordingPushBackend):
        assert len(backend.sent_messages) == 1
        msg = backend.sent_messages[0]
        assert msg["title"] == "System Alert"


def test_task_skipped_when_no_active_devices(make_user):
    """User without active devices logs and skips dispatch cleanly."""
    user = make_user()
    notif = Notification.objects.create(
        recipient=user,
        type=Notification.NotificationType.SYSTEM,
        title="System Notice",
        message="System alert body",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    result = send_push_notification.apply(args=[str(notif.id)]).get()
    assert result is False


def test_push_payload_carries_clean_template_zero_pii(make_user, make_post, make_device):
    """T-6.2-03: No comment body, preview, or actor name in title/body/data."""
    author = make_user()
    post = make_post(author=author, title="Safe Post Title")
    make_device(user=author, fcm_token="token_safe")

    notif = Notification.objects.create(
        recipient=author,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="John Doe commented on 'Safe Post Title': 'Sensitive body text'",
        message="John Doe commented on 'Safe Post Title': 'Sensitive body text'",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    result = send_push_notification.apply(args=[str(notif.id)]).get()
    assert result is True

    if isinstance(backend, RecordingPushBackend):
        assert len(backend.sent_messages) == 1
        msg = backend.sent_messages[0]
        # Verify title & body come from template, not from stored message
        assert msg["title"] == "New Discussion Reply"
        assert 'Someone commented on your post: "Safe Post Title"' in msg["body"]
        assert "Sensitive body text" not in msg["body"]
        assert "John Doe" not in msg["body"]
        assert "Sensitive body text" not in str(msg["data"])
        assert "John Doe" not in str(msg["data"])


def test_thread_debounce_suppresses_second_push_within_window(make_user, make_post, make_device):
    """D3: Second push on the same post within 15 minutes is debounced."""
    cache.clear()
    author = make_user()
    post = make_post(author=author)
    make_device(user=author, fcm_token="token_debounce")

    notif_1 = Notification.objects.create(
        recipient=author,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="Comment 1",
        message="Message 1",
    )
    notif_2 = Notification.objects.create(
        recipient=author,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="Comment 2",
        message="Message 2",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    res_1 = send_push_notification.apply(args=[str(notif_1.id)]).get()
    assert res_1 is True

    res_2 = send_push_notification.apply(args=[str(notif_2.id)]).get()
    assert res_2 is False

    if isinstance(backend, RecordingPushBackend):
        assert len(backend.sent_messages) == 1


def test_thread_debounce_exempts_vote_milestones(make_user, make_post, make_device):
    """D3: VOTE_MILESTONE is exempt from thread debounce even with post_id."""
    cache.clear()
    author = make_user()
    post = make_post(author=author)
    make_device(user=author, fcm_token="token_milestone")

    notif_comment = Notification.objects.create(
        recipient=author,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="Comment 1",
        message="Message 1",
    )
    notif_milestone = Notification.objects.create(
        recipient=author,
        post=post,
        type=Notification.NotificationType.VOTE_MILESTONE,
        title="Milestone 10",
        message="10 upvotes",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    res_1 = send_push_notification.apply(args=[str(notif_comment.id)]).get()
    assert res_1 is True

    res_2 = send_push_notification.apply(args=[str(notif_milestone.id)], kwargs={"count": 10}).get()
    assert res_2 is True

    if isinstance(backend, RecordingPushBackend):
        assert len(backend.sent_messages) == 2


def test_data_payload_structure_matches_spec_contract(make_user, make_post, make_device):
    """D16, §6.1: data dictionary carries notification_id, type, and click_action."""
    author = make_user()
    post = make_post(author=author)
    make_device(user=author, fcm_token="token_data")

    notif = Notification.objects.create(
        recipient=author,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="Test Title",
        message="Test Message",
    )

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()

    send_push_notification.apply(args=[str(notif.id)]).get()

    if isinstance(backend, RecordingPushBackend):
        data = backend.sent_messages[0]["data"]
        assert data["notification_id"] == str(notif.id)
        assert data["type"] == "COMMENT"
        assert data["click_action"] == f"/community/posts/{post.id}"
