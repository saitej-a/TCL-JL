"""Community services — the single write path for posts and comments (5.1 R1, R4).

`Model.clean()` is not called by `save()`, so a validator alone would leave the
reply-depth rule unenforced. These functions are where it actually runs: 5.2's
serializers delegate here (the 3.1/3.2 split — service owns the invariant,
serializer owns shape), and the model's `clean()` mirrors the same validators for
admin/forms.

Deliberately **not** here: rate limiting (5.2/T5.7), locked-post rejection and
commenter permissions (04 §42's *request-context* rules — 5.2/T5.10), and any
hard-delete path (5.1 D3/D4: removal is a flag, never a deletion).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models, transaction

from apps.community.models import Comment, Post
from apps.community.validators import (
    BLANK_CODE,
    CATEGORY_CODE,
    TITLE_LENGTH_CODE,
    validate_not_blank,
    validate_post_category,
    validate_reply_depth,
    validate_title_length,
)


class CommunityContentError(ValueError):
    """Base for rejected community content; `code` names the rule that failed.

    Plain `ValueError` with a stable `.code`, matching 3.1's
    `InvalidTransitionError`, so 5.2 renders the project envelope with a
    machine-readable code rather than a message string to pattern-match on.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class InvalidPostError(CommunityContentError):
    """A post could not be created (codes: blank_title, blank_body, title_too_long,
    invalid_category)."""


class InvalidCommentError(CommunityContentError):
    """A comment could not be created (codes: blank_body, nested_reply,
    parent_post_mismatch, parent_deleted)."""


# Validator codes → service codes, per field. Kept explicit so a code change is a
# deliberate, reviewable edit rather than an accidental rename.
_POST_CODES = {
    BLANK_CODE: {"title": "blank_title", "body": "blank_body"},
    TITLE_LENGTH_CODE: {"title": "title_too_long"},
    CATEGORY_CODE: {"category": "invalid_category"},
}


def _reject_post(field: str, error: DjangoValidationError) -> InvalidPostError:
    code = _POST_CODES.get(error.code, {}).get(field, error.code)
    return InvalidPostError(code, error.messages[0])


def _reject_comment(error: DjangoValidationError) -> InvalidCommentError:
    # The depth codes (nested_reply, parent_post_mismatch, parent_deleted) pass
    # through verbatim — they are already the contract 5.2 renders.
    code = "blank_body" if error.code == BLANK_CODE else error.code
    return InvalidCommentError(code, error.messages[0])


def create_post(author, *, title: str, body: str, category: str) -> Post:
    """Validate and persist a post (T5.1, T5.7's model half).

    `author` is passed in by the caller from the authentication context — never
    from a request body (06 §4.5), which is why it is a required argument here
    rather than a field any serializer could populate.
    """
    checks = (
        ("title", validate_not_blank, title),
        ("title", validate_title_length, title),
        ("body", validate_not_blank, body),
        ("category", validate_post_category, category),
    )
    for field, validator, value in checks:
        try:
            validator(value)
        except DjangoValidationError as exc:
            raise _reject_post(field, exc) from exc

    return Post.objects.create(author=author, title=title, body=body, category=category)


def create_comment(post: Post, author, *, body: str, parent: Comment | None = None) -> Comment:
    """Validate and persist a comment or reply (T5.2, T5.10's model half).

    The three depth rules come from 04 §42; the other two rules in that list (post
    not locked, user has permission) belong to the request layer and are 5.2's.
    """
    candidate = Comment(post=post, author=author, body=body, parent=parent)
    try:
        validate_not_blank(body)
    except DjangoValidationError as exc:
        raise _reject_comment(exc) from exc
    try:
        validate_reply_depth(candidate)
    except DjangoValidationError as exc:
        raise _reject_comment(exc) from exc

    with transaction.atomic():
        candidate.save()
        # Phase 6 hook: in-app notification + push enqueue (06.2 D10/D11)
        from apps.notifications.services import notify_comment_created

        notify_comment_created(candidate)

    return candidate


def soft_delete_post(post: Post) -> Post:
    """Flag a post as removed (COMM-05). Idempotent; the row is never deleted, and
    the original title/body stay in the database (08 §390).

    Reversal is simply `is_deleted = False` (08 §415) — a moderator correcting a
    mistake needs no special path, which is exactly why this must never become a
    hard delete.
    """
    return _soft_delete(post)


def soft_delete_comment(comment: Comment) -> Comment:
    """Flag a comment as removed, keeping `parent_id` so replies still resolve
    (5.1 D4 / roadmap criterion 4: tombstones preserve reply trees)."""
    return _soft_delete(comment)


def _soft_delete(content: models.Model):
    if not content.is_deleted:
        content.is_deleted = True
        content.save(update_fields=["is_deleted", "updated_at"])
    return content
