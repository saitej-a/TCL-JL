"""Moderation services (Phase 8.1 — MOD-01/MOD-03, 08 §3.3, 04 §63–§66).

The service owns the dedup query and the PENDING insert. Target resolution is
tombstone-inclusive BY DESIGN: 08 §3.3's flow has no deleted-content guard, and
a deleted scam post is exactly the evidence a moderator needs to see a report
about — the community helpers' `content_deleted` refusal must not leak here.
"""

from django.db import IntegrityError, transaction

from apps.community.models import Comment, Post
from apps.moderation.models import Report


class InvalidReportTarget(Exception):
    """Neither/both targets supplied, or an unknown reason value."""


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
