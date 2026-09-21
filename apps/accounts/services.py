"""Account lifecycle services (06 §2.4-§2.7, §3.4/§3.5; T2.5/T2.9/T2.11).

All email dispatch is deferred via ``transaction.on_commit`` so rolled-back
writes never emit mail, and goes through the Celery tasks in ``tasks.py``
(already routed in settings; plan deliverable 2).

Login credential checks ride Django's ``authenticate()`` (ModelBackend),
which hashes a dummy password for unknown users — constant-time behavior
against email enumeration (06 §2.4 rule 2).
"""

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import User
from apps.accounts.tasks import (
    send_password_reset_email,
    send_registration_collision_email,
    send_verification_email,
)

# Per-purpose salt (06 §2.5: salted TimestampSigner tokens).
EMAIL_VERIFY_SALT = "accounts.email-verify.v1"
EMAIL_VERIFY_MAX_AGE = 86400  # exactly 24 hours (AUTH-02)

GENERIC_VERIFICATION_MESSAGE = (
    "If an unverified account exists, a verification link has been sent."
)
GENERIC_RESET_MESSAGE = (
    "If an account exists with this email, password reset instructions have been dispatched."
)


# --- Token helpers -------------------------------------------------------------

def make_verification_token(user: User) -> str:
    signer = TimestampSigner(salt=EMAIL_VERIFY_SALT)
    return signer.sign(user.pk)


def read_verification_token(token: str) -> User:
    """Validate + consume a verification token (single-use semantics).

    Single-use is enforced by the target state: once ``is_verified`` is True
    the token can never flip anything, so reuse is rejected (06 §2.5).
    """
    signer = TimestampSigner(salt=EMAIL_VERIFY_SALT)
    try:
        pk = signer.unsign(token, max_age=EMAIL_VERIFY_MAX_AGE)
    except SignatureExpired as exc:
        raise ValueError("Verification link has expired.") from exc
    except BadSignature as exc:
        raise ValueError("Invalid verification token.") from exc

    user = User.objects.filter(pk=pk).first()
    if user is None:
        raise ValueError("Invalid verification token.")
    if user.is_verified:
        raise ValueError("Verification link has already been used.")
    return user


def make_password_reset_token(user: User) -> str:
    """06 §3.5 spec option 1: default_token_generator (HMAC of password hash,
    last_login, secret) packed as ``uidb64.token`` inside one token string.

    Hash rotation at confirm time inherently invalidates outstanding tokens.
    """
    return f"{urlsafe_base64_encode(force_bytes(user.pk))}.{default_token_generator.make_token(user)}"


def read_password_reset_token(token: str) -> User:
    try:
        uidb64, reset_token = token.split(".", 1)
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (ValueError, User.DoesNotExist, TypeError) as exc:
        raise ValueError("Invalid reset token.") from exc
    if not default_token_generator.check_token(user, reset_token):
        raise ValueError("Invalid or expired reset token.")
    return user


# --- Token revocation (06 §3.4 matrix) -----------------------------------------

def revoke_user_refresh_tokens(user: User) -> int:
    """Bulk-blacklist every outstanding refresh token for ``user``.

    Extracted now so the Phase 8 ban protocol (MOD-06) reuses it verbatim.
    """
    outstanding = OutstandingToken.objects.filter(user=user)
    return _bulk_blacklist(outstanding)


def blacklist_token_family(user_id, fam: str) -> int:
    """Blacklist every outstanding token of one token family (``fam`` claim).

    Family reuse-detection primitive (plan §1.3): when a rotated refresh is
    replayed, all descendants and siblings die with it.
    """
    outstanding = OutstandingToken.objects.filter(user_id=user_id)
    return _bulk_blacklist(outstanding, fam=fam)


def _bulk_blacklist(outstanding, fam: str | None = None) -> int:
    to_blacklist = []
    for token in outstanding:
        if fam is not None:
            try:
                payload = token_backend.decode(token.token, verify=False)
            except Exception:  # undecodable legacy row — not part of any family
                continue
            if payload.get("fam") != fam:
                continue
        to_blacklist.append(token)
    if not to_blacklist:
        return 0
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in to_blacklist],
        ignore_conflicts=True,  # already-blacklisted members are a no-op
    )
    return len(to_blacklist)


# --- Registration (06 §2.4, D1) -------------------------------------------------

def register_user(email: str, password: str) -> dict:
    """Create the account, or run the D1 collision branch.

    Returns ``{"created": bool, "user": User | None}``; the view renders the
    identical success body either way. Collision → notify the existing owner.
    """
    existing = User.objects.filter(email=email.strip().lower()).first()
    if existing is not None:
        transaction.on_commit(
            lambda: send_registration_collision_email.delay(str(existing.pk))
        )
        return {"created": False, "user": None}

    user = User.objects.create_user(email=email.strip().lower(), password=password)
    transaction.on_commit(lambda: send_verification_email.delay(str(user.pk)))
    return {"created": True, "user": user}


def dispatch_verification_email(user: User) -> None:
    transaction.on_commit(lambda: send_verification_email.delay(str(user.pk)))


# --- Verification (06 §2.5) ------------------------------------------------------

def verify_email(token: str) -> User:
    user = read_verification_token(token)
    user.is_verified = True
    user.save(update_fields=["is_verified", "updated_at"])
    return user


def resend_verification(email: str) -> None:
    """Generic response either way; email only for real unverified accounts."""
    user = User.objects.filter(email=email.strip().lower()).first()
    if user is not None and not user.is_verified:
        dispatch_verification_email(user)


# --- Password reset (06 §3.5, AUTH-03) -------------------------------------------

def request_password_reset(email: str) -> None:
    user = User.objects.filter(email=email.strip().lower()).first()
    if user is None or not user.is_active:
        return  # generic response either way (06 §3.5 rule 1)
    raw_token = make_password_reset_token(user)
    transaction.on_commit(
        lambda: send_password_reset_email.delay(str(user.pk), raw_token)
    )


def confirm_password_reset(raw_token: str, new_password: str) -> User:
    """Rotate the hash (killing outstanding reset tokens), re-validate the
    full password pipeline, and revoke all refresh tokens (06 §3.4 trigger 2).
    """
    user = read_password_reset_token(raw_token)
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    revoke_user_refresh_tokens(user)
    return user


# --- Change password (04 §77; shares revocation semantics) ------------------------

def change_password(user: User, current_password: str, new_password: str) -> None:
    if not user.check_password(current_password):
        raise ValueError("Current password is incorrect.")
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    revoke_user_refresh_tokens(user)


# --- Deletion (06 §2.7, AUTH-05) ---------------------------------------------------

DELETED_EMAIL_TEMPLATE = "deleted_{uuid}@tracker.internal"


def anonymize_delete_account(user: User, password: str) -> None:
    """Right-to-be-forgotten protocol (06 §2.7) as one atomic transaction.

    - Re-auth first (caller renders generic 403 on failure).
    - Device revocation hook: Device model arrives in Phase 6 (NOTIF); the
      Phase 6 executor adds ``user.devices.all().delete()`` here (see plan).
    - Bulk-blacklist all refresh tokens; invalidate credentials; anonymize
      email; retain the row as the Phase 5 tombstone seam (Post/Comment
      author FKs null or keep pointing at the anonymized user).
    """
    with transaction.atomic():
        # >>> Phase 6 hook: revoke all FCM device registrations here. <<<
        revoke_user_refresh_tokens(user)
        user.set_unusable_password()
        user.email = DELETED_EMAIL_TEMPLATE.format(uuid=uuid4().hex)
        user.is_active = False
        user.is_verified = False
        user.save(update_fields=["password", "email", "is_active", "is_verified", "updated_at"])
