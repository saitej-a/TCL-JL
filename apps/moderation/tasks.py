"""Moderation Celery tasks (Phase 8.2 — D1/D3, 08 §6 step 3 + §6.1 reinstatement).

Task names byte-match CELERY_TASK_ROUTES in config/settings/base.py:
- moderation.tasks.sever_banned_user_sessions (queue: default)
- moderation.tasks.auto_reinstate_users (queue: maintenance)

The 6.2/7.2 lesson: a decorator name off by one byte silently bypasses the
route table, so the names are spelled in full and asserted by a wiring test.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("moderation")


@shared_task(
    name="moderation.tasks.sever_banned_user_sessions",
    queue="default",
)
def sever_banned_user_sessions(user_id: str) -> dict[str, int]:
    """08 §6 step 3 — sever a banned user's sessions and device alerts.

    Idempotent by construction (D2): blacklisting an already-blacklisted token
    is a no-op in SimpleJWT, and deactivating an already-inactive device is a
    zero-row UPDATE. Re-running after a crash (or a deliberate re-ban) converges
    to the same end state.
    """
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    from apps.accounts.services import revoke_user_refresh_tokens
    from apps.notifications.models import Device

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        # Account deleted mid-flight — nothing to sever.
        logger.info("SEVER_SKIPPED_USER_GONE user_id=%s", user_id)
        return {"tokens": 0, "devices": 0}

    # revoke_user_refresh_tokens reports tokens *processed* (outstanding rows
    # survive blacklisting), so count the delta for an idempotent report: a
    # re-run after a crash blacklists nothing new and returns 0.
    already_blacklisted = BlacklistedToken.objects.filter(token__user=user).count()
    revoke_user_refresh_tokens(user)
    token_count = BlacklistedToken.objects.filter(token__user=user).count() - already_blacklisted
    device_count = Device.objects.filter(user=user, is_active=True).update(
        is_active=False, updated_at=timezone.now()
    )
    logger.info(
        "SEVERED_BANNED_USER_SESSIONS user_id=%s tokens_blacklisted=%d devices_deactivated=%d",
        user.pk,
        token_count,
        device_count,
    )
    return {"tokens": token_count, "devices": device_count}


@shared_task(
    name="moderation.tasks.auto_reinstate_users",
    queue="maintenance",
)
def auto_reinstate_users() -> int:
    """08 §6.1's temporary-suspension restoration: flip lapsed 7-day bans back.

    Only users with is_active=False AND banned_until <= now are touched —
    permanent bans (banned_until NULL) are never reinstated by the clock.
    """
    from django.contrib.auth import get_user_model

    from apps.moderation.services import reinstate_user

    User = get_user_model()
    now = timezone.now()
    lapsed = list(User.objects.filter(is_active=False, banned_until__lte=now))
    for user in lapsed:
        reinstate_user(user)
    if lapsed:
        logger.info("AUTO_REINSTATED_USERS count=%d", len(lapsed))
    return len(lapsed)
