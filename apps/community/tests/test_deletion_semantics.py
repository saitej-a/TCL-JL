"""Soft deletion + tombstones — COMM-05 (5.1 D3/D4; 03 §20, 08 §390-§415).

Two properties carry the requirement:

* **Nothing is physically removed.** The original text stays in the row for audit
  and legal review (08 §390), asserted here by reading the *raw* fields rather than
  through the display helpers — otherwise a masking bug could hide a deletion bug.
* **Nothing is attributed to the wrong actor.** One neutral copy serves an author's
  own deletion and a moderator's removal alike, because the single `is_deleted`
  flag cannot tell them apart (D3) — so no assertion should ever find the word
  "moderator" in the tombstone.
"""

import pytest

from apps.community.models import Comment, Post
from apps.community.services import soft_delete_comment, soft_delete_post
from apps.community.tombstones import TOMBSTONE_TEXT, display_body, display_title

pytestmark = pytest.mark.django_db


def test_soft_delete_post_flips_the_flag(make_post):
    post = make_post()

    soft_delete_post(post)

    post.refresh_from_db()
    assert post.is_deleted is True


def test_soft_delete_post_keeps_the_original_text_in_the_row(make_post):
    """08 §390: "Preserved for audit/legal". Masking happens on the way out, never
    by overwriting what the candidate wrote."""
    post = make_post(title="Real title", body="Real body")

    soft_delete_post(post)

    post.refresh_from_db()
    assert post.title == "Real title"
    assert post.body == "Real body"


def test_soft_delete_post_is_idempotent(make_post):
    post = make_post()
    soft_delete_post(post)
    post.refresh_from_db()
    first_stamp = post.updated_at

    soft_delete_post(post)

    post.refresh_from_db()
    assert post.is_deleted is True
    assert post.updated_at == first_stamp  # the second call writes nothing


def test_soft_delete_comment_flips_the_flag_and_keeps_the_body(make_post, make_comment):
    comment = make_comment(make_post(), body="Same here.")

    soft_delete_comment(comment)

    comment.refresh_from_db()
    assert comment.is_deleted is True
    assert comment.body == "Same here."


def test_display_title_masks_only_when_deleted(make_post):
    post = make_post(title="Real title")

    assert display_title(post) == "Real title"

    soft_delete_post(post)
    post.refresh_from_db()

    assert display_title(post) == TOMBSTONE_TEXT


def test_display_body_masks_a_deleted_post(make_post):
    post = make_post(body="Real body")
    soft_delete_post(post)

    post.refresh_from_db()
    assert display_body(post) == TOMBSTONE_TEXT


def test_display_body_masks_a_deleted_comment(make_post, make_comment):
    comment = make_comment(make_post(), body="Same here.")

    assert display_body(comment) == "Same here."

    soft_delete_comment(comment)
    comment.refresh_from_db()
    assert display_body(comment) == TOMBSTONE_TEXT


def test_tombstone_makes_no_moderation_claim():
    """D3: the copy is neutral because the flag cannot distinguish an author's
    deletion from a moderator's removal. 08 §406's moderator wording would have
    made a candidate's own deletion display a claim that never happened."""
    assert TOMBSTONE_TEXT == "This content has been removed."
    assert "moderator" not in TOMBSTONE_TEXT.lower()


def test_tombstoned_comment_keeps_its_reply_tree(make_post, make_comment):
    """Roadmap success criterion 4: reply hierarchies survive a tombstone."""
    post = make_post()
    parent = make_comment(post)
    reply = make_comment(post, parent=parent)

    soft_delete_comment(parent)

    parent.refresh_from_db()
    reply.refresh_from_db()
    assert parent.parent_id is None  # it was top-level; nothing rewired it
    assert reply.parent_id == parent.id
    assert list(parent.replies.all()) == [reply]
    assert post.comments.count() == 2


def test_tombstoned_post_keeps_its_comments(make_post, make_comment):
    post = make_post()
    make_comment(post)

    soft_delete_post(post)

    assert post.comments.count() == 1


def test_soft_deletion_never_removes_rows(make_post, make_comment):
    post = make_post()
    comment = make_comment(post)

    soft_delete_post(post)
    soft_delete_comment(comment)

    assert Post.objects.count() == 1
    assert Comment.objects.count() == 1


def test_reversal_restores_the_content(make_post, make_comment):
    """08 §415: correcting a mistaken removal is literally flipping the flag back —
    which is only possible because the text was never overwritten."""
    post = make_post(title="Real title", body="Real body")
    comment = make_comment(post, body="Same here.")
    soft_delete_post(post)
    soft_delete_comment(comment)

    post.refresh_from_db()
    comment.refresh_from_db()
    post.is_deleted = False
    comment.is_deleted = False
    post.save(update_fields=["is_deleted"])
    comment.save(update_fields=["is_deleted"])

    assert display_title(post) == "Real title"
    assert display_body(post) == "Real body"
    assert display_body(comment) == "Same here."


def test_deleted_content_still_carries_its_author_and_timestamps(make_post, make_comment):
    """Nothing about removal detaches attribution or history (D2: the anonymized
    user row is the tombstone for *account* deletion, not this flag)."""
    post = make_post()
    author_id = post.author_id
    created = post.created_at

    soft_delete_post(post)

    post.refresh_from_db()
    assert post.author_id == author_id
    assert post.created_at == created
