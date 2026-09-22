"""Model structure, delete behaviour, and schema invariants (T5.1-T5.3; 5.1 D2, P1-P4).

The delete-behaviour tests are the ones that encode decisions rather than fields:
`PROTECT` on authors is what makes the anonymized-row tombstone policy (D2)
enforced instead of merely documented, and `SET_NULL` on `parent` is what keeps a
hard delete from ever destroying a reply (P1).
"""

import uuid
from pathlib import Path

import pytest
from django.db.models import ProtectedError

from apps.community.models import Comment, Post, PostVote

pytestmark = pytest.mark.django_db

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "0001_initial.py"

INDEX_NAMES = {
    "idx_post_category_created",
    "idx_post_created",
    "idx_post_pinned_created",
    "idx_comment_post_created",
    "idx_comment_parent_created",
}


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_uuid_v4_primary_keys_are_assigned(make_post, make_comment, make_vote):
    post = make_post()
    comment = make_comment(post)
    vote = make_vote(post.author, post)

    for obj in (post, comment, vote):
        assert isinstance(obj.pk, uuid.UUID)
        assert obj.pk.version == 4, obj


def test_moderation_and_deletion_flags_default_to_false(make_orm_post):
    post = make_orm_post()

    assert post.is_pinned is False
    assert post.is_locked is False
    assert post.is_deleted is False


def test_related_names_match_the_community_surface(make_user, make_post, make_comment, make_vote):
    author = make_user()
    post = make_post(author=author)
    comment = make_comment(post, author)
    vote = make_vote(author, post)

    assert list(post.comments.all()) == [comment]
    assert list(post.votes.all()) == [vote]
    assert list(author.community_posts.all()) == [post]
    assert list(author.community_comments.all()) == [comment]
    assert list(author.post_votes.all()) == [vote]


def test_parent_related_name_is_replies(make_post, make_comment):
    parent = make_comment(make_post())
    reply = make_comment(parent.post, parent=parent)

    assert list(parent.replies.all()) == [reply]
    assert reply.parent_id == parent.id


def test_post_ordering_pins_first_then_newest(make_post, make_orm_post):
    """03 §17 builds `(is_pinned, created_at)` for this order, and 5.2's
    pagination depends on it being stable."""
    oldest = make_post(title="First posted")
    newest = make_post(title="Second posted")
    pinned = make_orm_post(title="Pinned notice", is_pinned=True)

    assert list(Post.objects.all()) == [pinned, newest, oldest]


def test_comment_ordering_is_chronological(make_post, make_comment):
    post = make_post()
    first = make_comment(post, body="first")
    second = make_comment(post, body="second")

    assert list(Comment.objects.all()) == [first, second]


def test_indexes_declared_and_present_in_initial_migration():
    """Both levels: the model declares them *and* the generated migration carries
    them, so a refreshed database really has the query paths 5.2 relies on."""
    declared = {index.name for index in Post._meta.indexes}
    declared |= {index.name for index in Comment._meta.indexes}
    assert declared == INDEX_NAMES

    migration = _migration_text()
    for name in INDEX_NAMES:
        assert f"name='{name}'" in migration, name


def test_vote_uniqueness_is_a_named_database_constraint():
    constraint = next(
        c for c in PostVote._meta.constraints if getattr(c, "name", "") == "unique_user_post_vote"
    )

    assert constraint.fields == ("user", "post")
    assert "name='unique_user_post_vote'" in _migration_text()


def test_no_denormalized_counters_exist():
    """03 §9/§29/§30: counts are aggregated, never stored, so they cannot drift."""
    post_fields = {field.name for field in Post._meta.get_fields()}

    assert "vote_count" not in post_fields
    assert "comment_count" not in post_fields


def test_category_has_no_choices_so_settings_changes_need_no_migration():
    """D1's whole point: the vocabulary is settings-held, so extending it must not
    produce a migration. A `choices=` argument would be frozen into 0001_initial."""
    assert Post._meta.get_field("category").choices is None
    # Nothing in the migration freezes a vocabulary: the field is a plain CharField.
    assert "choices" not in _migration_text()


def test_author_is_protected_from_hard_user_deletion(make_post):
    """D2: the anonymized row is the tombstone, so deleting a User must not be
    possible while they authored content — the DB refuses instead of nulling."""
    post = make_post()

    with pytest.raises(ProtectedError):
        post.author.delete()

    assert Post.objects.filter(id=post.id).exists()


def test_comment_author_is_protected_too(make_post, make_comment):
    comment = make_comment(make_post())

    with pytest.raises(ProtectedError):
        comment.author.delete()

    assert Comment.objects.filter(id=comment.id).exists()


def test_hard_deleting_a_post_cascades_comments_and_votes(make_post, make_comment, make_vote):
    """03 §19: Post → Comment and Post → Vote are CASCADE. Harmless on the normal
    path (removal is a flag, D4), but it is what keeps a genuinely removed thread
    from leaving orphan rows behind."""
    post = make_post()
    make_comment(post)
    make_vote(post.author, post)

    post.delete()

    assert Comment.objects.count() == 0
    assert PostVote.objects.count() == 0
