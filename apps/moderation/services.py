"""Moderation services (Phase 8.1 — MOD-01/MOD-03, 08 §3.3; Phase 8.2 — MOD-05/06, 08 §4, §6).

The 8.1 service owns the dedup query and the PENDING insert. Target resolution is
tombstone-inclusive BY DESIGN: 08 §3.3's flow has no deleted-content guard, and
a deleted scam post is exactly the evidence a moderator needs to see a report
about — the community helpers' `content_deleted` refusal must not leak here.

Phase 8.2 adds the enforcement half (CONTEXT D1–D6, D9): `ban_user`/`unban_user`
(the single ban writers, shared by REST and Admin), `resolve_report` (the five
triage actions, one writer for the REST review endpoint and the Admin bulk
actions), and `log_moderation_action` (§11.1 structured logging — the audit
trail is log events; no AuditLog model, D9).
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.community.models import Comment, Post
from apps.moderation.models import Report

logger = logging.getLogger("moderation")


class InvalidReportTarget(Exception):
    """Neither/both targets supplied, an unknown reason, or an invalid action."""


class DuplicateReportError(Exception):
    """The reporter already has a PENDING report on this target (08 §3.3)."""


def create_report(
    reporter,
    *,
    post=None,
    comment=None,
    reason: str,
    description: str = "",
) -> Report:
    """Create a PENDING report against exactly one post or comment.

    Double-enforced dedup (5.1 P4 parity): the §3.3 query check raises a typed
    error for the friendly envelope, and the conditional UniqueConstraints
    convert a concurrent-race IntegrityError into the same error.
    """
    if (post is None) == (comment is None):
        raise InvalidReportTarget(
            "A report must target either a post or a comment, not both or neither."
        )
    if reason not in Report.ReportReason.values:
        raise InvalidReportTarget(f"Unknown report reason: {reason}")

    # Resolve the rows directly — tombstoned targets stay reportable (evidence).
    if post is not None:
        target = Post.objects.filter(id=post.pk if hasattr(post, "pk") else post).first()
        if target is None:
            raise InvalidReportTarget("Post not found.")
    else:
        comment_id = comment.pk if hasattr(comment, "pk") else comment
        target = Comment.objects.filter(id=comment_id).first()
        if target is None:
            raise InvalidReportTarget("Comment not found.")

    existing = Report.objects.filter(reporter=reporter, status=Report.ReportStatus.PENDING)
    existing = (
        existing.filter(post_id=target.pk)
        if post is not None
        else existing.filter(comment_id=target.pk)
    )
    if existing.exists():
        raise DuplicateReportError("You already have a pending report for this content.")

    try:
        with transaction.atomic():
            return Report.objects.create(
                reporter=reporter,
                post=target if post is not None else None,
                comment=target if comment is not None else None,
                reason=reason,
                description=description[:1000],
                status=Report.ReportStatus.PENDING,
            )
    except IntegrityError as exc:
        # Race: two concurrent identical reports; the pending-unique constraints
        # decide. Same envelope, same semantics as the pre-check.
        raise DuplicateReportError("You already have a pending report for this content.") from exc


# --- Phase 8.2: structured moderation logging (D9, 08 §11.1) -----------------------

ACTIONS = ("DISMISS", "REMOVE_CONTENT", "LOCK_POST", "WARN_USER", "BAN_USER")


def log_moderation_action(
    *,
    moderator,
    action: str,
    reason: str = "",
    notes: str = "",
    report=None,
    target=None,
) -> None:
    """Emit one §11.1-shaped JSON event on the `moderation` logger (D9).

    The durable per-report record is Report.reviewed_by/reviewed_at/
    moderator_notes; this log line doubles as §6 step 1's "AuditLog entry".
    """
    target_type = ""
    target_id = ""
    if report is not None:
        if report.post_id:
            target_type, target_id = "POST", str(report.post_id)
        elif report.comment_id:
            target_type, target_id = "COMMENT", str(report.comment_id)
    elif target is not None:
        target_type, target_id = type(target).__name__.upper(), str(target.pk)
    event = {
        "event": "MODERATION_ACTION_TAKEN",
        "moderator_id": str(moderator.pk),
        "report_id": str(report.pk) if report is not None else None,
        "target_type": target_type,
        "target_id": target_id,
        "action": action,
        "reason": reason or (report.reason if report is not None else ""),
        "notes": (notes or "")[:200],
    }
    # extra= attaches the §11.1 keys to the LogRecord itself, so log processors
    # (and tests) can filter on structured fields without parsing the message.
    logger.info("MODERATION_ACTION_TAKEN %s", event, extra=event)


# --- Phase 8.2: ban protocol (D1/D2/D3, 08 §6) -------------------------------------


class ModerationTargetError(Exception):
    """A ban was attempted on a staff member or the moderator themself (04 §70)."""


def _dispatch_sever_task(user_id: str) -> None:
    """Import-and-dispatch the sever task (lazy import: no task→service cycle)."""
    from apps.moderation.tasks import sever_banned_user_sessions

    sever_banned_user_sessions.delay(str(user_id))


def ban_user(moderator, user, *, reason: str, duration_days: int = 0, report=None) -> None:
    """08 §6 step 1 — one transaction: is_active=False + banned_until + log line.

    Step 3 (token blacklist + device deactivation) is the Celery task dispatched
    via on_commit — so a caller already inside an outer atomic block never
    dispatches a sever for a ban that rolls back (D1). Idempotent: re-banning
    re-fires the sever task (D2). Refuses staff members and the moderator
    themself (04 §70's privilege-escalation bar).
    """
    if getattr(user, "is_staff", False):
        raise ModerationTargetError("Staff members cannot be banned through this action.")
    if user.pk == moderator.pk:
        raise ModerationTargetError("You cannot ban your own account.")

    with transaction.atomic():
        user.is_active = False
        if duration_days and duration_days > 0:
            user.banned_until = timezone.now() + timedelta(days=int(duration_days))
        else:
            # Permanent — 08 §6.1: restoration by admin manual review only.
            user.banned_until = None
        user.save(update_fields=["is_active", "banned_until", "updated_at"])
        log_moderation_action(
            moderator=moderator,
            action="BAN_USER",
            reason=reason,
            notes=f"duration_days={duration_days}" if duration_days else "permanent",
            report=report,
            target=user,
        )
    transaction.on_commit(lambda: _dispatch_sever_task(user.pk))


def unban_user(moderator, user) -> None:
    """Reinstate an account (D2): is_active=True, banned_until cleared.

    Devices and token blacklists are deliberately NOT touched — re-registration
    is the sanctioned path; the severing stays one-way.
    """
    with transaction.atomic():
        user.is_active = True
        user.banned_until = None
        user.save(update_fields=["is_active", "banned_until", "updated_at"])
        log_moderation_action(moderator=moderator, action="UNBAN", target=user)


def reinstate_user(user) -> None:
    """Auto-reinstatement writer (system actor, 08 §6.1's 7-day level)."""
    with transaction.atomic():
        user.is_active = True
        user.banned_until = None
        user.save(update_fields=["is_active", "banned_until", "updated_at"])
    event = {
        "event": "MODERATION_ACTION_TAKEN",
        "moderator_id": "system",
        "report_id": None,
        "target_type": "USER",
        "target_id": str(user.pk),
        "action": "AUTO_REINSTATE",
        "reason": "",
        "notes": "",
    }
    logger.info("MODERATION_ACTION_TAKEN %s", event, extra=event)


# --- Phase 8.2: report triage actions (D4/D5, 08 §4.2) -----------------------------


def _notify_moderation(*, recipient, message: str, post=None, comment=None):
    """Create the author's MODERATION notification (8.1's dormant type goes live).

    No `actor`: §4.2.2/§4.2.4 dispatch from the system, so self-action
    suppression must never swallow it. The push enqueue rides on
    create_notification's on_commit and carries only the fixed MODERATION
    template text (zero-PII, 6.2 D5).
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import create_notification

    return create_notification(
        recipient,
        notification_type=Notification.NotificationType.MODERATION,
        title="Moderation Notice",
        message=message,
        post=post,
        comment=comment,
    )


def resolve_report(
    report,
    moderator,
    *,
    action: str,
    moderator_notes: str = "",
    duration_days: int = 0,
):
    """The five triage actions (D4) — one writer for REST review and Admin actions.

    DISMISS → status DISMISSED; the other four → RESOLVED (§3.2's labels).
    Every path writes reviewed_by/reviewed_at/moderator_notes and emits the
    §11.1 log line; the report row and the action effect commit together.
    LOCK_POST on a comment-targeted report raises (and rolls the status write
    back) — the view translates that into a 400.
    """
    if action not in ACTIONS:
        raise InvalidReportTarget(f"Unknown moderation action: {action}")

    now = timezone.now()
    notes = (moderator_notes or "")[:1000]

    def _apply_status(target_status: str) -> None:
        report.status = target_status
        report.reviewed_by = moderator
        report.reviewed_at = now
        report.moderator_notes = notes
        report.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "moderator_notes", "updated_at"]
        )

    if action == "DISMISS":
        with transaction.atomic():
            _apply_status(Report.ReportStatus.DISMISSED)
            log_moderation_action(moderator=moderator, action=action, notes=notes, report=report)
        return report

    with transaction.atomic():
        _apply_status(Report.ReportStatus.RESOLVED)
        log_moderation_action(moderator=moderator, action=action, notes=notes, report=report)

        if action == "REMOVE_CONTENT":
            target = report.post or report.comment
            target.is_deleted = True
            target.save(update_fields=["is_deleted", "updated_at"])
            # §4.2.2: notify the author with the reason. Idempotent on
            # tombstones — a re-flag simply re-resolves the report.
            if report.post_id and report.post.author_id:
                _notify_moderation(
                    recipient=report.post.author,
                    message=(
                        "Your post was removed by a moderator for violating "
                        f"community guidelines (Reason: {report.reason})."
                    ),
                    post=report.post,
                )
            elif report.comment_id and report.comment.author_id:
                _notify_moderation(
                    recipient=report.comment.author,
                    message=(
                        "Your comment was removed by a moderator for violating "
                        f"community guidelines (Reason: {report.reason})."
                    ),
                    comment=report.comment,
                )
        elif action == "LOCK_POST":
            if not report.post_id:
                raise InvalidReportTarget("LOCK_POST applies only to post-targeted reports.")
            report.post.is_locked = True
            report.post.save(update_fields=["is_locked", "updated_at"])
        elif action == "WARN_USER":
            target = report.post or report.comment
            _notify_moderation(
                recipient=target.author,
                message=(
                    "You have received a formal warning from the moderators "
                    "for violating community guidelines."
                ),
                post=report.post,
                comment=report.comment,
            )
        elif action == "BAN_USER":
            # §4.2.5: the ban is about the content author. ban_user dispatches
            # the sever task on commit of THIS outermost transaction (D1).
            content = report.post or report.comment
            ban_user(
                moderator,
                content.author,
                reason=report.reason,
                duration_days=duration_days,
                report=report,
            )
    return report
