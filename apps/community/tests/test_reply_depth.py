"""Strict 1-level replies — T5.2 + 04 §42's three model-level rules (COMM-03).

04 §42 lists five rules for creating a comment; three of them are about the parent
and belong to the model layer, which is what this file covers:

1. ``nested_reply`` — the parent must be top-level.
2. ``parent_post_mismatch`` — the parent must be on the same post.
3. ``parent_deleted`` — a removed comment accepts no new replies.

The other two (post not locked, user has permission) are request-context rules and
land with 5.2's endpoints. Every rejection is asserted to persist *nothing*, since
a validator that raises after a partial write protects nothing.
"""

import uuid

import pytest
from django.core.exceptions import ValidationError

from apps.community.models import Comment, PostVote
from apps.community.services import InvalidCommentError, create_comment, soft_delete_comment
from apps.community.validators import (
    NESTED_REPLY_CODE,
    PARENT_DELETED_CODE,
    PARENT_MISMATCH_CODE,
    validate_reply_depth,
)

pytestmark = pytest.mark.django_db


def test_top_level_comment_is_accepted(make_post, make_comment):
    post = make_post()

    comment = make_comment(post)

    assert comment.parent_id is None
    assert post.comments.count() == 1


def test_reply_to_a_top_level_comment_is_accepted(make_post, make_comment):
    post = make_post()
    parent = make_comment(post)

    reply = make_comment(post, parent=parent)

    assert reply.parent_id == parent.id
    assert list(parent.replies.all()) == [reply]


def test_reply_to_a_reply_is_rejected_and_persists_nothing(make_post, make_comment, make_user):
    """T5.2's exact rule: `parent.parent` must be None."""
    post = make_post()
    parent = make_comment(post)
    reply = make_comment(post, parent=parent)

    with pytest.raises(InvalidCommentError) as exc:
        create_comment(post, make_user(), body="Nested attempt", parent=reply)

    assert exc.value.code == NESTED_REPLY_CODE
    assert Comment.objects.filter(body="Nested attempt").count() == 0


def test_parent_from_another_post_is_rejected(make_post, make_comment, make_user):
    first, second = make_post(), make_post()
    foreign_parent = make_comment(first)

    with pytest.raises(InvalidCommentError) as exc:
        create_comment(second, make_user(), body="Wrong thread", parent=foreign_parent)

    assert exc.value.code == PARENT_MISMATCH_CODE
    assert second.comments.count() == 0


def test_reply_to_a_soft_deleted_parent_is_rejected(make_post, make_comment, make_user):
    """The tombstone stays visible in the thread (D4), but the conversation under
    it is closed — a removed comment accepts no new replies (04 §42)."""
    post = make_post()
    parent = make_comment(post)
    soft_delete_comment(parent)

    with pytest.raises(InvalidCommentError) as exc:
        create_comment(post, make_user(), body="Too late", parent=parent)

    assert exc.value.code == PARENT_DELETED_CODE


def test_live_parent_on_a_soft_deleted_post_still_accepts_replies(make_post, make_comment):
    """Only the *parent's* state matters. Comments on a removed post stay readable
    and usable, which is what keeps a deleted post's thread coherent (D4)."""
    post = make_post()
    parent = make_comment(post)
    post.is_deleted = True
    post.save(update_fields=["is_deleted", "updated_at"])

    reply = make_comment(post, parent=parent)

    assert reply.parent_id == parent.id


def test_model_clean_raises_the_same_machine_readable_codes(make_post, make_comment):
    """The admin/form path must not degrade to generic 'invalid' codes — a caller
    checking `code` has to get the same answer on both paths."""
    post = make_post()
    reply = make_comment(post, parent=make_comment(post))
    nested = Comment(post=post, author=post.author, body="Nested", parent=reply)

    with pytest.raises(ValidationError) as exc:
        nested.full_clean()

    assert exc.value.error_dict["parent"][0].code == NESTED_REPLY_CODE


def test_clean_reports_a_deleted_parent_with_its_code(make_post, make_comment):
    post = make_post()
    parent = make_comment(post)
    soft_delete_comment(parent)
    candidate = Comment(post=post, author=post.author, body="reply", parent=parent)

    with pytest.raises(ValidationError) as exc:
        candidate.full_clean()

    assert exc.value.error_dict["parent"][0].code == PARENT_DELETED_CODE


def test_depth_resolution_is_attribute_based_not_ancestor_walking(make_post, make_user):
    """O(1) by construction: only `parent.parent_id` is read, so the check works on
    objects that were never saved and never issues an ancestor query."""
    post = make_post()
    transient_parent = Comment(post=post, author=make_user(), body="not saved yet")

    legal = Comment(post=post, author=make_user(), body="reply", parent=transient_parent)
    validate_reply_depth(legal)  # no error

    transient_parent.parent_id = uuid.uuid4()  # now it *is* a reply
    illegal = Comment(post=post, author=make_user(), body="reply", parent=transient_parent)
    with pytest.raises(ValidationError) as exc:
        validate_reply_depth(illegal)

    assert exc.value.code == NESTED_REPLY_CODE


def test_hard_deleting_a_parent_promotes_its_reply(make_post, make_comment):
    """P1's whole justification for SET_NULL: a disappearing parent can never take
    a legitimate reply with it. The reply is promoted to top-level instead."""
    post = make_post()
    parent = make_comment(post)
    reply = make_comment(post, parent=parent, body="Please don't delete me")

    parent.delete()

    reply.refresh_from_db()
    assert reply.parent_id is None
    assert reply.body == "Please don't delete me"
    assert post.comments.count() == 1


def test_post_deletion_is_never_blocked_by_depth(make_post, make_comment):
    """P1 rejected PROTECT because, combined with Post → Comment CASCADE, it would
    raise ProtectedError and make removing a two-level thread impossible."""
    post = make_post()
    make_comment(post, parent=make_comment(post))
    PostVote.objects.create(user=post.author, post=post)

    post.delete()  # must not raise

    assert Comment.objects.count() == 0
    assert PostVote.objects.count() == 0
