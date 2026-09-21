"""Transactional email tasks (T2.5) — names already routed in settings.

``send_verification_email`` / ``send_password_reset_email`` were reserved by
Phase 1.6 Celery routing; ``send_registration_collision_email`` is the one
additive route this phase (D1 collision notice). Console backend in dev means
emails surface in worker logs (Stage 2 drill watches for them there).
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.accounts.models import User

logger = logging.getLogger(__name__)

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost")


def _user_email(user_id: str) -> str:
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        logger.warning("accounts.tasks: user %s disappeared before email dispatch", user_id)
        return None
    return user.email


@shared_task(name="accounts.tasks.send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, user_id: str) -> str | None:
    email = _user_email(user_id)
    if email is None:
        return None
    from apps.accounts.services import make_verification_token

    token = make_verification_token(User.objects.get(pk=user_id))
    verify_url = f"{FRONTEND_URL}/verify-email/{token}"
    body = render_to_string(
        "account/emails/email_verification.txt", {"verify_url": verify_url}
    )
    send_mail(
        subject="Verify your TCS Joining Tracker account",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info("verification email dispatched to %s", email)
    return token


@shared_task(name="accounts.tasks.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, user_id: str, raw_token: str) -> None:
    email = _user_email(user_id)
    if email is None:
        return
    reset_url = f"{FRONTEND_URL}/reset-password/{raw_token}"
    body = render_to_string(
        "account/emails/password_reset.txt", {"reset_url": reset_url}
    )
    send_mail(
        subject="Reset your TCS Joining Tracker password",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info("password reset email dispatched to %s", email)


@shared_task(name="accounts.tasks.send_registration_collision_email", bind=True, max_retries=3)
def send_registration_collision_email(self, user_id: str) -> None:
    """D1: notify the existing owner that someone tried to register their address."""
    email = _user_email(user_id)
    if email is None:
        return
    body = render_to_string("account/emails/registration_collision.txt", {})
    send_mail(
        subject="A registration attempt was made with your email",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info("registration collision notice dispatched to %s", email)
