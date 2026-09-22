"""Tests for in-app notification creation, composition, suppression, and enqueue (Phase 6.2)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.db import transaction

from apps.candidates.models import CandidateProfile
from apps.community.models import Comment
from apps.notifications.models import Notification
from apps.notifications.services import (
    PREVIEW_LENGTH,
    PUSH_TEXT_TEMPLATES,
    create_notification,
    maybe_notify_vote_milestone,
    notify_comment_created,
)


@pytest.fixture(autouse=True)
def mock_tasks_delay(monkeypatch):
    """Stub the task delay call so on_commit triggers without requiring Celery broker."""
    mock_task = MagicMock()
    monkeypatch.setattr(
        "apps.notifications.services.send_push_notification",
        mock_task,
        raising=False,
    )
    # Also patch inside sys.modules if needed
    return mock_task


def test_push_text_templates_contains_all_seven_types():
    expected_types = {
        Notification.NotificationType.COMMENT,
        Notification.NotificationType.REPLY,
        Notification.NotificationType.VOTE_MILESTONE,
        Notification.NotificationType.ANNOUNCEMENT,
        Notification.NotificationType.MODERATION,
        Notification.NotificationType.TIMELINE_REMINDER,
        Notification.NotificationType.SYSTEM,
    }
    assert set(PUSH_TEXT_TEMPLATES.keys()) == expected_types
    for _n_type, (title, body) in PUSH_TEXT_TEMPLATES.items():
        assert isinstance(title, str) and title
        assert isinstance(body, str) and body


def test_peer_comment_creates_comment_notification_with_exact_text(
    make_user, make_post, make_comment
):
    author_post = make_user()
    author_comment = make_user()
    post = make_post(author=author_post, title="TCS Joining 2026")
    comment = make_comment(post=post, author=author_comment, body="Got my ILP date!")

    notif = notify_comment_created(comment)

    assert notif is not None
    assert notif.recipient == author_post
    assert notif.type == Notification.NotificationType.COMMENT
    assert notif.title == "New Comment on Your Post"
    assert notif.post == post
    assert notif.comment == comment
    assert notif.is_read is False
    assert notif.read_at is None

    # Public label from resolve_public_display_name
    assert f"commented on '{post.title}': 'Got my ILP date!'" in notif.message


def test_reply_creates_reply_notification_for_parent_author_only(
    make_user, make_post, make_comment
):
    author_post = make_user()
    author_parent = make_user()
    author_reply = make_user()

    post = make_post(author=author_post, title="Discussion Thread")
    parent_comment = make_comment(post=post, author=author_parent, body="Initial comment.")
    reply = Comment.objects.create(
        post=post,
        author=author_reply,
        parent=parent_comment,
        body="Reply to initial comment.",
    )

    notif = notify_comment_created(reply)

    assert notif is not None
    assert notif.recipient == author_parent
    assert notif.type == Notification.NotificationType.REPLY
    assert notif.title == "New Reply to Your Comment"
    assert notif.post == post
    assert notif.comment == reply
    expected_msg = f"replied to your comment on '{post.title}': 'Reply to initial comment.'"
    assert expected_msg in notif.message

    # Post author gets no duplicate notification for reply (D12)
    assert not Notification.objects.filter(recipient=author_post).exists()


def test_display_name_uses_public_label_never_email(make_user, make_post, make_comment):
    author_post = make_user()
    actor = make_user(email="secretive_actor@example.com")
    CandidateProfile.objects.create(
        user=actor,
        display_name="Secret Candidate",
        public_identity_mode=CandidateProfile.PublicIdentityMode.ANONYMOUS,
    )

    post = make_post(author=author_post)
    comment = make_comment(post=post, author=actor, body="Testing privacy boundary.")

    notif = notify_comment_created(comment)

    assert notif is not None
    assert "secretive_actor@example.com" not in notif.message
    assert "Secret Candidate" not in notif.message  # anonymous mode -> Anonymous Candidate
    assert "Anonymous Candidate commented on" in notif.message


def test_comment_preview_truncated_at_80_with_ellipsis(make_user, make_post, make_comment):
    post = make_post()
    actor = make_user()
    long_body = "A" * 120
    comment = make_comment(post=post, author=actor, body=long_body)

    notif = notify_comment_created(comment)

    assert notif is not None
    expected_preview = ("A" * PREVIEW_LENGTH) + "..."
    assert f"': '{expected_preview}'" in notif.message


def test_comment_preview_shorter_than_80_has_no_ellipsis(make_user, make_post, make_comment):
    post = make_post()
    actor = make_user()
    short_body = "Short comment."
    comment = make_comment(post=post, author=actor, body=short_body)

    notif = notify_comment_created(comment)

    assert notif is not None
    assert f"': '{short_body}'" in notif.message
    assert "..." not in notif.message


def test_self_comment_suppressed(make_user, make_post, make_comment):
    author = make_user()
    post = make_post(author=author)
    comment = make_comment(post=post, author=author, body="My own post update.")

    notif = notify_comment_created(comment)

    assert notif is None
    assert Notification.objects.count() == 0


def test_self_reply_suppressed(make_user, make_post, make_comment):
    post_author = make_user()
    comment_author = make_user()
    post = make_post(author=post_author)
    parent = make_comment(post=post, author=comment_author, body="My thoughts.")
    reply = Comment.objects.create(
        post=post,
        author=comment_author,
        parent=parent,
        body="Replying to myself.",
    )

    notif = notify_comment_created(reply)

    assert notif is None
    assert Notification.objects.count() == 0


def test_create_notification_actor_equals_recipient_returns_none(make_user):
    user = make_user()
    result = create_notification(
        user,
        notification_type=Notification.NotificationType.SYSTEM,
        title="Alert",
        message="System alert",
        actor=user,
    )
    assert result is None
    assert Notification.objects.count() == 0


def test_create_notification_nullable_post_and_comment_for_system_types(make_user):
    recipient = make_user()
    notif = create_notification(
        recipient,
        notification_type=Notification.NotificationType.SYSTEM,
        title="System Notice",
        message="Scheduled maintenance tomorrow.",
    )
    assert notif is not None
    assert notif.post is None
    assert notif.comment is None
    assert notif.type == Notification.NotificationType.SYSTEM


def test_create_notification_timeline_reminder_type(make_user):
    recipient = make_user()
    notif = create_notification(
        recipient,
        notification_type=Notification.NotificationType.TIMELINE_REMINDER,
        title="Timeline Reminder",
        message="It has been a while since you updated your timeline.",
    )
    assert notif is not None
    assert notif.type == Notification.NotificationType.TIMELINE_REMINDER


def test_create_notification_moderation_type(make_user):
    recipient = make_user()
    notif = create_notification(
        recipient,
        notification_type=Notification.NotificationType.MODERATION,
        title="Moderation Notice",
        message="Your content was flagged for review.",
    )
    assert notif is not None
    assert notif.type == Notification.NotificationType.MODERATION


def test_create_notification_announcement_type(make_user):
    recipient = make_user()
    notif = create_notification(
        recipient,
        notification_type=Notification.NotificationType.ANNOUNCEMENT,
        title="Community Update",
        message="New joining batch guidelines released.",
    )
    assert notif is not None
    assert notif.type == Notification.NotificationType.ANNOUNCEMENT


def test_on_commit_enqueue_fires_delay_with_row_id(
    make_user, make_post, make_comment, django_capture_on_commit_callbacks, mock_tasks_delay
):
    author_post = make_user()
    author_comment = make_user()
    post = make_post(author=author_post)
    comment = make_comment(post=post, author=author_comment, body="Hello")

    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            notif = notify_comment_created(comment)

    assert notif is not None
    mock_tasks_delay.delay.assert_called_once_with(str(notif.id))


def test_on_commit_enqueue_suppressed_call_fires_nothing(
    make_user, make_post, make_comment, django_capture_on_commit_callbacks, mock_tasks_delay
):
    author = make_user()
    post = make_post(author=author)
    comment = make_comment(post=post, author=author, body="Self comment")

    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            notif = notify_comment_created(comment)

    assert notif is None
    mock_tasks_delay.delay.assert_not_called()


def test_milestone_enqueue_carries_count_in_kwargs(
    make_user, make_post, django_capture_on_commit_callbacks, mock_tasks_delay
):
    author = make_user()
    voter = make_user()
    post = make_post(author=author)

    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            notif = maybe_notify_vote_milestone(post, voter, previous_count=9, current_count=10)

    assert notif is not None
    mock_tasks_delay.delay.assert_called_once_with(str(notif.id), count=10)


def test_stored_snapshot_is_immutable_on_subsequent_post_edit(make_user, make_post, make_comment):
    author_post = make_user()
    author_comment = make_user()
    post = make_post(author=author_post, title="Original Post Title")
    comment = make_comment(post=post, author=author_comment, body="Nice info")

    notif = notify_comment_created(comment)
    assert notif is not None
    assert "Original Post Title" in notif.message

    # Edit post title
    post.title = "Completely Changed Title"
    post.save()

    # Notification message stays unchanged
    notif.refresh_from_db()
    assert "Original Post Title" in notif.message
    assert "Completely Changed Title" not in notif.message


def test_stored_snapshot_is_immutable_on_subsequent_comment_edit(
    make_user, make_post, make_comment
):
    author_post = make_user()
    author_comment = make_user()
    post = make_post(author=author_post, title="Joining Date")
    comment = make_comment(post=post, author=author_comment, body="First draft")

    notif = notify_comment_created(comment)
    assert notif is not None
    assert "First draft" in notif.message

    # Edit comment body
    comment.body = "Edited comment body"
    comment.save()

    notif.refresh_from_db()
    assert "First draft" in notif.message
    assert "Edited comment body" not in notif.message


def test_nested_reply_notifies_immediate_parent_author(make_user, make_post, make_comment):
    post_author = make_user()
    c1_author = make_user()
    c2_author = make_user()
    c3_author = make_user()

    post = make_post(author=post_author)
    c1 = make_comment(post=post, author=c1_author, body="Root")
    c2 = Comment.objects.create(post=post, author=c2_author, parent=c1, body="Level 1")
    c3 = Comment.objects.create(post=post, author=c3_author, parent=c2, body="Level 2")

    notif = notify_comment_created(c3)

    assert notif is not None
    assert notif.recipient == c2_author
    assert notif.type == Notification.NotificationType.REPLY
    assert not Notification.objects.filter(recipient=c1_author).exists()
    assert not Notification.objects.filter(recipient=post_author).exists()


def test_reply_to_post_author_comment_uses_reply_type(make_user, make_post, make_comment):
    post_author = make_user()
    responder = make_user()

    post = make_post(author=post_author)
    # Post author comments on their own post
    parent = make_comment(post=post, author=post_author, body="My comment")

    # Another user replies to post author's comment
    reply = Comment.objects.create(post=post, author=responder, parent=parent, body="Reply to you")

    notif = notify_comment_created(reply)

    assert notif is not None
    assert notif.recipient == post_author
    assert notif.type == Notification.NotificationType.REPLY
    assert notif.title == "New Reply to Your Comment"


def test_notification_defaults_unread_state(make_user):
    user = make_user()
    notif = create_notification(
        user,
        notification_type=Notification.NotificationType.SYSTEM,
        title="Title",
        message="Msg",
    )
    assert notif is not None
    assert notif.is_read is False
    assert notif.read_at is None
    assert notif.recipient == user


def test_inapp_row_persists_even_if_push_backend_fails(
    make_user, make_post, make_comment, django_capture_on_commit_callbacks, monkeypatch
):
    """Proves D3/acceptance criteria: in-app rows exist regardless of push outcome."""
    author = make_user()
    actor = make_user()
    post = make_post(author=author)
    comment = make_comment(post=post, author=actor)

    mock_failing_task = MagicMock()
    mock_failing_task.delay.side_effect = RuntimeError("Redis unavailable")
    monkeypatch.setattr(
        "apps.notifications.services.send_push_notification",
        mock_failing_task,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="Redis unavailable"):
        with django_capture_on_commit_callbacks(execute=True):
            with transaction.atomic():
                notify_comment_created(comment)

    # In-app row was committed to DB before the on_commit handler raised
    assert Notification.objects.filter(recipient=author).exists()
