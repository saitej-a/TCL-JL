"""`unique_user_post_vote` — the phase's database-level guarantee (COMM-04, T5.3).

The distinction these tests defend: duplicate votes must be impossible *at the
database level*, not merely rejected by a serializer or a service. Every case here
writes through the ORM directly (bypassing `full_clean`) precisely so the failure
has to come from PostgreSQL.

`IntegrityError` marks the connection as needing rollback, so each failing write is
wrapped in its own `transaction.atomic()` block — otherwise the assertion would
poison the surrounding test transaction.
"""

import pytest
from django.db import IntegrityError, transaction
from django.db.models import Count

from apps.community.models import PostVote

pytestmark = pytest.mark.django_db


def test_duplicate_vote_is_rejected_by_the_database(make_user, make_post, make_vote):
    """Roadmap criterion 3, at the layer that actually holds: a second row for the
    same (user, post) raises IntegrityError and leaves exactly one vote."""
    user = make_user()
    post = make_post(author=user)
    make_vote(user, post)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PostVote.objects.create(user=user, post=post)

    assert PostVote.objects.filter(user=user, post=post).count() == 1


def test_bulk_create_of_duplicate_votes_also_fails(make_user, make_post):
    """Bulk writes skip per-row ORM validation entirely — an application-level
    check would not fire here, but the constraint still does."""
    user = make_user()
    post = make_post(author=user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PostVote.objects.bulk_create(
                [PostVote(user=user, post=post), PostVote(user=user, post=post)]
            )

    assert PostVote.objects.count() == 0


def test_two_users_may_vote_the_same_post(make_user, make_post, make_vote):
    post = make_post(author=make_user())
    first, second = make_user(), make_user()

    make_vote(first, post)
    make_vote(second, post)

    assert post.votes.count() == 2


def test_one_user_may_vote_two_posts(make_user, make_post, make_vote):
    user = make_user()
    first, second = make_post(author=user), make_post(author=user)

    make_vote(user, first)
    make_vote(user, second)

    assert user.post_votes.count() == 2


def test_constraint_is_declared_exactly_once_with_the_spec_name():
    names = [getattr(c, "name", None) for c in PostVote._meta.constraints]

    assert names == ["unique_user_post_vote"]


def test_soft_deleting_a_post_retains_its_votes(make_user, make_post, make_vote):
    """Removal is a flag (5.1 D4), so nothing cascades — and a restored post gets
    its vote count back exactly as it was (08 §415)."""
    user = make_user()
    post = make_post(author=user)
    make_vote(user, post)

    post.is_deleted = True
    post.save(update_fields=["is_deleted", "updated_at"])

    assert PostVote.objects.filter(post=post).count() == 1


def test_vote_count_is_derivable_by_aggregation(make_user, make_post, make_vote):
    """03 §29: counts come from `annotate(Count(...))`, so no denormalized column
    has to be kept in sync with the constraint."""
    post = make_post(author=make_user())
    for _ in range(3):
        make_vote(make_user(), post)
    make_vote(make_user(), make_post(author=make_user()))  # noise on another post

    annotated = PostVote.objects.filter(post=post).aggregate(total=Count("id"))

    assert annotated["total"] == 3
