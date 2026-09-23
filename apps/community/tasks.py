"""Community Celery tasks (Phase 8.2 — T8.6/T8.10; 08 §7).

Named entries that must byte-match their wiring:

* ``community.tasks.clean_expired_announcements`` — reserved in
  ``config/celery.py``'s beat schedule (hourly :15) since Phase 1.2 and inert
  until this module existed. The 7.2 lesson: a decorator name off by one byte
  silently drops the routing/beat entry.
* ``broadcast_announcement_dispatch`` — the thin seam `Announcement.publish()`
  calls. It reads ``settings.ANNOUNCEMENT_PUSH_CHUNK`` and forwards to
  ``notifications.tasks.broadcast_announcement`` (the byte-exact reserved route
  name lives there; the fan-out belongs to the push app, the trigger to this one).
  Keeping the seam separate is what lets tests assert "publish dispatched exactly
  once" without standing up the whole fan-out.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("community")


@shared_task(name="community.tasks.clean_expired_announcements", queue="maintenance")
def clean_expired_announcements() -> int:
    """Unpublish announcements whose `expires_at` has lapsed (08 §7's lifecycle).

    Unpublish, never delete: the row (and the moderator's wording) stays for
    review, and 04 §72's public read already hides non-published rows.
    """
    from apps.community.models import Announcement

    now = timezone.now()
    expired = Announcement.objects.filter(is_published=True, expires_at__lt=now)
    count = expired.update(is_published=False, updated_at=now)
    if count:
        logger.info("CLEANED_EXPIRED_ANNOUNCEMENTS count=%d", count)
    return count


def broadcast_announcement_dispatch(announcement_id: str) -> None:
    """Fire the announcement fan-out (called by ``Announcement.publish()``).

    Lazy import so ``community.models`` never imports the notifications app at
    module load (keeping the app graph one-directional), and so tests can patch
    this single seam to prove the publish transition dispatches exactly once.
    """
    from apps.notifications.tasks import broadcast_announcement

    logger.info(
        "ANNOUNCEMENT_BROADCAST_DISPATCHED announcement_id=%s chunk=%d",
        announcement_id,
        getattr(settings, "ANNOUNCEMENT_PUSH_CHUNK", 500),
    )
    broadcast_announcement.delay(announcement_id)
