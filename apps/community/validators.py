"""Community content validators (T5.2; 5.1 D1, P4, R4).

These raise Django's `ValidationError` so they work from both `Model.clean()`
(admin/forms) and the service functions; the services translate their codes into
the community error vocabulary (see `services.py`).

The reply-depth rule is the interesting one: 04 §42 lists three model-level rules
for creating a comment, and all three are checked here from **ids** — never by
walking ancestors — so the check is O(1) and safe on unsaved instances.
"""

from django.conf import settings
from django.core.exceptions import ValidationError

# Pinned by 5.1 R3 (the specs only said "String, Required").
TITLE_MAX_LENGTH = 200

CATEGORY_CODE = "invalid_category"
BLANK_CODE = "blank_content"
TITLE_LENGTH_CODE = "title_too_long"
NESTED_REPLY_CODE = "nested_reply"
PARENT_MISMATCH_CODE = "parent_post_mismatch"
PARENT_DELETED_CODE = "parent_deleted"


def post_categories() -> list[tuple[str, str]]:
    """The (key, label) vocabulary, read at call time (5.1 D1).

    Reading the setting per call — rather than importing it at module scope — is
    what lets ops add a category with no code change and no migration, and lets
    tests exercise that with `override_settings`. 5.2's categories endpoint serves
    this same structure.
    """
    return list(getattr(settings, "POST_CATEGORIES", []))


def post_category_keys() -> set[str]:
    return {key for key, _label in post_categories()}


def validate_post_category(value) -> None:
    """Reject any category outside the settings-held vocabulary."""
    if value not in post_category_keys():
        raise ValidationError(
            f"Unknown post category: {value!r}.",
            code=CATEGORY_CODE,
        )


def validate_not_blank(value) -> None:
    """Reject empty, whitespace-only, and missing content (title or body)."""
    if value is None or not str(value).strip():
        raise ValidationError("This field may not be blank.", code=BLANK_CODE)


def validate_title_length(value) -> None:
    """Reject an over-long title with a stable code (Django's own `max_length`
    message would otherwise be the only signal)."""
    if value is not None and len(str(value)) > TITLE_MAX_LENGTH:
        raise ValidationError(
            f"Title may not exceed {TITLE_MAX_LENGTH} characters.",
            code=TITLE_LENGTH_CODE,
        )


def validate_reply_depth(comment) -> None:
    """Enforce T5.2 + 04 §42's three reply rules, in a fixed order.

    1. ``nested_reply`` — the parent is already a reply (strict 1-level nesting).
    2. ``parent_post_mismatch`` — the parent belongs to a different post.
    3. ``parent_deleted`` — the parent is soft-deleted; a removed comment accepts
       no new replies (its tombstone stays visible in the thread, but the
       conversation under it is closed).

    A `None` parent (a top-level comment) is always valid.
    """
    parent = comment.parent
    if parent is None:
        return

    if parent.parent_id is not None:
        raise ValidationError(
            "A reply cannot itself be a reply to another reply.",
            code=NESTED_REPLY_CODE,
        )

    post_id = comment.post_id if comment.post_id is not None else getattr(comment.post, "pk", None)
    if post_id is None or parent.post_id != post_id:
        raise ValidationError(
            "The parent comment belongs to a different post.",
            code=PARENT_MISMATCH_CODE,
        )

    if parent.is_deleted:
        raise ValidationError(
            "This comment has been removed and cannot receive replies.",
            code=PARENT_DELETED_CODE,
        )
