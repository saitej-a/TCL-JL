"""Notifications service layer (Phase 6.2 — decisions D3–D5, D10–D12).

Honours 6.1 D4's anonymity-safe composition contract and D5's two-text rule:
- create_notification(): stores in-app snapshot with actor suppression and on_commit push enqueue.
- notify_comment_created(): COMMENT / REPLY notification dispatch with display name resolution.
- maybe_notify_vote_milestone(): threshold watermark deduplication for post upvote milestones.
- register_device(): last-writer-wins FCM token registration and reassignment (D6).
- PUSH_TEXT_TEMPLATES: fixed per-type templates for push payloads.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.candidates.models import resolve_public_display_name
from apps.notifications.models import Device, Notification

logger = logging.getLogger("notifications")

# D5 — The only source of push text (07 §4.1 push column)
PUSH_TEXT_TEMPLATES: dict[str, tuple[str, str]] = {
    Notification.NotificationType.COMMENT: (
        "New Discussion Reply",
        'Someone commented on your post: "{title}"',
    ),
    Notification.NotificationType.REPLY: (
        "New Reply Received",
        "Someone replied to your comment in the TCS Joining Tracker community.",
    ),
    Notification.NotificationType.VOTE_MILESTONE: (
        "Discussion Trending",
        "Your post reached {count} upvotes in the community tracker.",
    ),
    Notification.NotificationType.ANNOUNCEMENT: (
        "Community Update",
        "A new community update has been published.",
    ),
    Notification.NotificationType.MODERATION: (
        "Moderation Notice",
        "There is an update about your content.",
    ),
    Notification.NotificationType.TIMELINE_REMINDER: (
        "Timeline Reminder",
        "It has been a while since you updated your timeline.",
    ),
    Notification.NotificationType.SYSTEM: (
        "System Alert",
        "You have a new system notification.",
    ),
}

PREVIEW_LENGTH = 80  # comment/reply preview inside the in-app message (07 §4.1.1)
TITLE_PUSH_TRUNCATE = 60  # lock-screen title truncation
BODY_PUSH_TRUNCATE = 120  # lock-screen body truncation


def _enqueue(notification_id: str, push_context: dict[str, Any] | None = None) -> None:
    """Enqueue asynchronous push delivery task via Celery."""
    try:
        from apps.notifications.tasks import send_push_notification
    except (ImportError, ModuleNotFoundError):
        send_push_notification = globals().get("send_push_notification")
        if send_push_notification is None:
            logger.debug(
                "send_push_notification task not found; skipping enqueue for %s",
                notification_id,
            )
            return

    kwargs = dict(push_context) if push_context else {}
    send_push_notification.delay(notification_id, **kwargs)


def create_notification(
    recipient,
    *,
    notification_type: str | Notification.NotificationType,
    title: str,
    message: str,
    post=None,
    comment=None,
    actor=None,
    push_context: dict[str, Any] | None = None,
) -> Notification | None:
    """Create a stored in-app notification snapshot and enqueue push.

    Fires on transaction commit (D11/D12).
    Returns None if actor == recipient (self-action suppression, 07 §14.1.1).
    """
    if actor is not None and recipient is not None:
        actor_id = getattr(actor, "pk", actor)
        recipient_id = getattr(recipient, "pk", recipient)
        if actor_id == recipient_id:
            return None

    notification = Notification.objects.create(
        recipient=recipient,
        type=str(notification_type),
        title=title,
        message=message,
        post=post,
        comment=comment,
    )

    ctx = dict(push_context) if push_context else None
    transaction.on_commit(lambda: _enqueue(str(notification.id), ctx))
    return notification


def notify_comment_created(comment) -> Notification | None:
    """Create notification and enqueue push for comment / reply events (D12)."""
    actor = comment.author
    post = comment.post
    display_name = resolve_public_display_name(actor)
    raw_content = getattr(comment, "body", "") or getattr(comment, "content", "")
    preview = (
        raw_content[:PREVIEW_LENGTH] + "..." if len(raw_content) > PREVIEW_LENGTH else raw_content
    )

    if comment.parent is None:
        recipient = post.author
        if actor == recipient:
            return None
        title = "New Comment on Your Post"
        message = f"{display_name} commented on '{post.title}': '{preview}'"
        return create_notification(
            recipient,
            notification_type=Notification.NotificationType.COMMENT,
            title=title,
            message=message,
            post=post,
            comment=comment,
            actor=actor,
        )
    else:
        recipient = comment.parent.author
        if actor == recipient:
            return None
        title = "New Reply to Your Comment"
        message = f"{display_name} replied to your comment on '{post.title}': '{preview}'"
        return create_notification(
            recipient,
            notification_type=Notification.NotificationType.REPLY,
            title=title,
            message=message,
            post=post,
            comment=comment,
            actor=actor,
        )


def maybe_notify_vote_milestone(
    post,
    actor,
    previous_count: int,
    current_count: int,
) -> Notification | None:
    """Create notification when upvote count crosses milestone thresholds (D4).

    Dedupes against existing VOTE_MILESTONE rows for post (watermark rule).
    Author's own upvote crossing is suppressed absolutely.
    """
    if actor == post.author:
        return None

    thresholds = getattr(
        settings,
        "VOTE_MILESTONE_THRESHOLDS",
        [10, 25, 50, 100, 250, 500],
    )
    crossed_candidates = [t for t in thresholds if previous_count < t <= current_count]
    if not crossed_candidates:
        return None

    crossed = max(crossed_candidates)
    threshold_idx = thresholds.index(crossed)

    watermark = Notification.objects.filter(
        post=post,
        type=Notification.NotificationType.VOTE_MILESTONE,
    ).count()

    if threshold_idx < watermark:
        return None

    title = "Upvote Milestone Reached"
    message = f"Your discussion '{post.title}' has reached {crossed} upvotes!"

    return create_notification(
        post.author,
        notification_type=Notification.NotificationType.VOTE_MILESTONE,
        title=title,
        message=message,
        post=post,
        actor=actor,
        push_context={"count": crossed},
    )


def register_device(
    user,
    *,
    fcm_token: str,
    device_type: str = "WEB",
    browser: str = "",
) -> tuple[Device, bool]:
    """Register or reassign an FCM device token (D6 last-writer-wins).

    Returns (device, created). Both paths return 201 at the endpoint boundary.
    """
    fcm_token = fcm_token.strip()
    device = Device.objects.filter(fcm_token=fcm_token).first()
    now = timezone.now()
    if device is not None:
        device.user = user
        device.is_active = True
        device.browser = browser
        device.device_type = device_type
        device.last_seen_at = now
        device.save(
            update_fields=[
                "user",
                "is_active",
                "browser",
                "device_type",
                "last_seen_at",
                "updated_at",
            ]
        )
        return device, False

    device = Device.objects.create(
        user=user,
        fcm_token=fcm_token,
        device_type=device_type,
        browser=browser,
        is_active=True,
        last_seen_at=now,
    )
    return device, True
