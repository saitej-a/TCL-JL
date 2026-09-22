"""Tests for stale token deactivation, pruning, zero-token logging,
and community producer hooks (Phase 6.2).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.community.services import create_comment
from apps.community.views_services import DuplicateVoteError, vote_post
from apps.notifications.backends import RecordingPushBackend, SendResult
from apps.notifications.models import Device, Notification
from apps.notifications.tasks import prune_stale_devices, send_push_notification


def test_invalid_tokens_are_deactivated_with_updated_at(make_user, make_post, make_device):
    """R9, §13.1: Stale/unregistered tokens deactivated; survivors untouched."""
    user = make_user()
    post = make_post(author=user)
    device_good = make_device(user=user, fcm_token="good_token_abc")
    device_bad = make_device(user=user, fcm_token="bad_token_xyz")

    notif = Notification.objects.create(
        recipient=user,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="Test",
        message="Test msg",
    )

    mock_result = SendResult(
        success_count=1,
        failure_count=1,
        failed_tokens=("bad_token_xyz",),
    )

    with patch("apps.notifications.tasks.get_push_backend") as mock_get_backend:
        mock_backend = RecordingPushBackend()
        mock_backend.send_multicast = lambda *a, **kw: mock_result
        mock_get_backend.return_value = mock_backend

        send_push_notification.apply(args=[str(notif.id)]).get()

    device_good.refresh_from_db()
    device_bad.refresh_from_db()

    assert device_good.is_active is True
    assert device_bad.is_active is False
    assert device_bad.updated_at > device_bad.created_at


def test_zero_token_strings_appear_in_logs(make_user, make_post, make_device, caplog):
    """R9, §13.1: Task logs carry ids and counts, never raw FCM token strings."""
    user = make_user()
    post = make_post(author=user)
    secret_token = "fcm_very_private_token_99999"
    make_device(user=user, fcm_token=secret_token)

    notif = Notification.objects.create(
        recipient=user,
        post=post,
        type=Notification.NotificationType.COMMENT,
        title="Test",
        message="Test msg",
    )

    with caplog.at_level(logging.DEBUG):
        send_push_notification.apply(args=[str(notif.id)]).get()

    for record in caplog.records:
        assert secret_token not in record.message


def test_prune_stale_devices_task(make_user, make_device):
    """07 §7.2, §10.1: Prunes inactive devices older than 30 days only."""
    user = make_user()
    now = timezone.now()

    # Inactive > 30 days -> should be deleted
    d_stale = make_device(user=user, fcm_token="stale_token", is_active=False)
    Device.objects.filter(id=d_stale.id).update(updated_at=now - timedelta(days=35))

    # Inactive < 30 days -> should be kept
    d_recent = make_device(user=user, fcm_token="recent_token", is_active=False)
    Device.objects.filter(id=d_recent.id).update(updated_at=now - timedelta(days=10))

    # Active -> should be kept
    d_active = make_device(user=user, fcm_token="active_token", is_active=True)
    Device.objects.filter(id=d_active.id).update(updated_at=now - timedelta(days=40))

    pruned = prune_stale_devices.apply().get()
    assert pruned == 1

    assert not Device.objects.filter(id=d_stale.id).exists()
    assert Device.objects.filter(id=d_recent.id).exists()
    assert Device.objects.filter(id=d_active.id).exists()


def test_create_comment_producer_creates_inapp_notification(make_user, make_post):
    """Community create_comment producer hook creates in-app notification for post author."""
    author = make_user()
    commenter = make_user()
    post = make_post(author=author, title="Production Post")

    comment = create_comment(post, commenter, body="Great progress on the joining tracker!")

    notif = Notification.objects.filter(recipient=author, post=post, comment=comment).first()
    assert notif is not None
    assert notif.type == Notification.NotificationType.COMMENT
    assert notif.is_read is False


def test_create_reply_producer_targets_parent_author_only(make_user, make_post):
    """D12: Reply creates notification for parent comment author only, not post author."""
    post_author = make_user()
    parent_author = make_user()
    replier = make_user()

    post = make_post(author=post_author)
    parent_comment = create_comment(post, parent_author, body="Original comment")

    # Clear notifications from parent creation
    Notification.objects.all().delete()

    reply = create_comment(post, replier, body="Direct reply", parent=parent_comment)

    # Parent author receives notification
    notif = Notification.objects.filter(recipient=parent_author, comment=reply).first()
    assert notif is not None
    assert notif.type == Notification.NotificationType.REPLY

    # Post author receives no extra notification
    assert not Notification.objects.filter(recipient=post_author, comment=reply).exists()


def test_community_vote_triggers_milestone_and_preserves_duplicate_error(make_user, make_post):
    """vote_post triggers milestone notification on threshold and preserves 409."""
    author = make_user()
    voters = [make_user() for _ in range(10)]
    post = make_post(author=author, title="Milestone Target")

    # Cast 9 votes directly
    for v in voters[:9]:
        post.votes.create(user=v)

    assert post.votes.count() == 9
    assert not Notification.objects.filter(
        post=post, type=Notification.NotificationType.VOTE_MILESTONE
    ).exists()

    # 10th vote via vote_post
    vote_post(voters[9], post)

    notif = Notification.objects.filter(
        recipient=author,
        post=post,
        type=Notification.NotificationType.VOTE_MILESTONE,
    ).first()
    assert notif is not None
    assert "10 upvotes" in notif.message

    # Duplicate vote still raises DuplicateVoteError (5.1 P3)
    with pytest.raises(DuplicateVoteError):
        vote_post(voters[9], post)
