"""Celery background tasks for push notification delivery and device maintenance.

Task names byte-match CELERY_TASK_ROUTES in config/settings/base.py:
- notifications.tasks.send_push_notification (queue: notifications)
- notifications.tasks.prune_stale_devices (queue: maintenance)

07 §5.1 sample names (notifications.send_push_notification) would silently
bypass the Celery routing configuration. We preserve the full module path.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.notifications.backends import get_push_backend
from apps.notifications.models import Device, Notification, NotificationPreference
from apps.notifications.services import PUSH_TEXT_TEMPLATES

logger = logging.getLogger("notifications")


@shared_task(
    bind=True,
    name="notifications.tasks.send_push_notification",
    autoretry_for=(Exception,),
    max_retries=getattr(settings, "PUSH_MAX_RETRIES", 3),
    retry_backoff=True,
    retry_backoff_max=60,
    queue="notifications",
)
def send_push_notification(self, notification_id: str, **kwargs: Any) -> bool:
    """Asynchronously delivers a web push notification to active recipient devices."""
    try:
        notification = (
            Notification.objects.select_related("recipient", "post")
            .filter(id=notification_id)
            .first()
        )
    except Exception as exc:
        logger.warning("Notification %s query failed: %s; discarding task.", notification_id, exc)
        return False

    if notification is None:
        logger.warning("Notification %s does not exist; discarding task.", notification_id)
        return False

    recipient = notification.recipient

    # 1. Check user preferences (D14)
    pref = getattr(recipient, "notification_preferences", None)
    if pref is None:
        pref, _ = NotificationPreference.get_or_create_for(recipient)

    if not pref.push_enabled:
        logger.info("PUSH_SKIPPED_PREFERENCES: push disabled globally for user %s", recipient.id)
        return False

    # Category checks
    notif_type = notification.type
    if notif_type == Notification.NotificationType.COMMENT and not pref.notify_on_comment:
        logger.info("PUSH_SKIPPED_PREFERENCES: comment push disabled for user %s", recipient.id)
        return False
    if notif_type == Notification.NotificationType.REPLY and not pref.notify_on_reply:
        logger.info("PUSH_SKIPPED_PREFERENCES: reply push disabled for user %s", recipient.id)
        return False
    if (
        notif_type == Notification.NotificationType.VOTE_MILESTONE
        and not pref.notify_on_vote_milestone
    ):
        logger.info(
            "PUSH_SKIPPED_PREFERENCES: milestone push disabled for user %s",
            recipient.id,
        )
        return False
    if (
        notif_type == Notification.NotificationType.ANNOUNCEMENT
        and not pref.notify_on_announcements
    ):
        logger.info(
            "PUSH_SKIPPED_PREFERENCES: announcement push disabled for user %s",
            recipient.id,
        )
        return False
    if (
        notif_type == Notification.NotificationType.TIMELINE_REMINDER
        and not pref.notify_timeline_reminders
    ):
        logger.info(
            "PUSH_SKIPPED_PREFERENCES: timeline reminder push disabled for user %s",
            recipient.id,
        )
        return False

    # 2. Fetch active devices for recipient
    devices = list(Device.objects.filter(user=recipient, is_active=True))
    if not devices:
        logger.debug("PUSH_SKIPPED_NO_DEVICES: user %s has no active push devices.", recipient.id)
        return False

    # 3. Debounce check for thread pushes (D3)
    # Only COMMENT and REPLY on a specific post are debounced within 15 minutes.
    # VOTE_MILESTONE and post-less notifications are exempt.
    if (
        notif_type in (Notification.NotificationType.COMMENT, Notification.NotificationType.REPLY)
        and notification.post_id
    ):
        debounce_key = f"debounce_push_post_{recipient.id}_{notification.post_id}"
        debounce_ttl = getattr(settings, "THREAD_PUSH_DEBOUNCE_SECONDS", 900)
        if not cache.add(debounce_key, 1, timeout=debounce_ttl):
            logger.info(
                "PUSH_SUPPRESSED_DEBOUNCE: thread push debounced for recipient %s on post %s",
                recipient.id,
                notification.post_id,
            )
            return False

    # 4. Construct clean zero-PII lock-screen push payload (D5, T-6.2-03, §8)
    template_title, template_body = PUSH_TEXT_TEMPLATES.get(
        notif_type,
        ("Notification", "You have a new update in TCS Joining Tracker."),
    )

    title = template_title
    if notif_type == Notification.NotificationType.COMMENT:
        post_title = (
            notification.post.title if notification.post else str(kwargs.get("title", "your post"))
        )
        if len(post_title) > 60:
            post_title = post_title[:57] + "..."
        body = f'Someone commented on your post: "{post_title}"'
    elif notif_type == Notification.NotificationType.VOTE_MILESTONE:
        count = kwargs.get("count")
        if not count and notification.post:
            count = notification.post.votes.count()
        count_val = count if count else 10
        body = f"Your post reached {count_val} upvotes in the community tracker."
    else:
        body = template_body

    data_payload = {
        "notification_id": str(notification.id),
        "type": str(notification.type),
        "click_action": (
            f"/community/posts/{notification.post_id}" if notification.post_id else "/dashboard"
        ),
    }

    tokens = [d.fcm_token for d in devices]

    # 5. Dispatch via PushBackend seam
    backend = get_push_backend()
    start_time = time.monotonic()
    result = backend.send_multicast(tokens=tokens, title=title, body=body, data=data_payload)
    duration_ms = int((time.monotonic() - start_time) * 1000)

    # 6. Deactivate stale tokens (R9, §13.1)
    if result.invalid_tokens:
        Device.objects.filter(fcm_token__in=result.invalid_tokens).update(
            is_active=False,
            updated_at=timezone.now(),
        )

    logger.info(
        "PUSH_NOTIFICATION_SENT: notification_id=%s recipient_id=%s "
        "sent=%d failed=%d invalid=%d duration_ms=%d",
        notification.id,
        recipient.id,
        result.success_count,
        result.failure_count,
        len(result.invalid_tokens),
        duration_ms,
    )

    if (
        result.retryable_tokens
        and hasattr(self, "request")
        and self.request.retries < self.max_retries
    ):
        raise self.retry(countdown=2**self.request.retries)

    return True


@shared_task(
    name="notifications.tasks.prune_stale_devices",
    queue="maintenance",
)
def prune_stale_devices() -> int:
    """Deletes inactive devices older than 30 days (07 §7.2, §10.1)."""
    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = Device.objects.filter(
        is_active=False,
        updated_at__lt=cutoff,
    ).delete()
    logger.info("PRUNED_STALE_DEVICES: deleted=%d cutoff=%s", deleted_count, cutoff)
    return deleted_count
