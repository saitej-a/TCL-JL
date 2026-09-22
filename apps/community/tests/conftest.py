"""Shared fixtures for the community test suite (5.1).

Two post/comment factories on purpose, so a test's intent is visible: `make_post`
and `make_comment` go through the services (the real write path with its
validation), while `make_orm_post` / `make_orm_comment` write directly — needed by
constraint and flag tests that must bypass application validation to prove what
the *database* enforces.
"""

import pytest

from apps.accounts.models import User
from apps.community.models import Comment, Post, PostVote
from apps.community.services import create_comment, create_post

VALID_PASSWORD = "Correct Horse Battery 9!"


def _new_user(suffix: str) -> User:
    return User.objects.create_user(
        f"cm-{suffix}-{User.objects.count()}@example.com", VALID_PASSWORD, is_verified=True
    )


@pytest.fixture
def make_user(db):
    def _make(email: str | None = None, **overrides) -> User:
        if email is None:
            return _new_user("user")
        defaults = dict(is_verified=True)
        defaults.update(overrides)
        return User.objects.create_user(email, VALID_PASSWORD, **defaults)

    return _make


@pytest.fixture
def make_post(db):
    """Create a post through the service (the validated write path)."""

    def _make(
        author=None,
        *,
        title="Joining letter updates?",
        body="Anyone heard back?",
        category="JOINING_LETTER",
    ) -> Post:
        if author is None:
            author = _new_user("post")
        return create_post(author, title=title, body=body, category=category)

    return _make


@pytest.fixture
def make_orm_post(db):
    """Create a post directly, bypassing service validation."""

    def _make(author=None, **overrides) -> Post:
        if author is None:
            author = _new_user("ormpost")
        defaults = dict(
            title="Joining letter updates?",
            body="Anyone heard back?",
            category="JOINING_LETTER",
        )
        defaults.update(overrides)
        return Post.objects.create(author=author, **defaults)

    return _make


@pytest.fixture
def make_comment(db):
    """Create a comment through the service (the validated write path)."""

    def _make(
        post: Post, author=None, *, body="Same here.", parent: Comment | None = None
    ) -> Comment:
        if author is None:
            author = _new_user("comment")
        return create_comment(post, author, body=body, parent=parent)

    return _make


@pytest.fixture
def make_orm_comment(db):
    """Create a comment directly, bypassing service validation."""

    def _make(post: Post, author=None, **overrides) -> Comment:
        if author is None:
            author = _new_user("ormcomment")
        defaults = dict(body="Same here.", parent=None)
        defaults.update(overrides)
        return Comment.objects.create(post=post, author=author, **defaults)

    return _make


@pytest.fixture
def make_vote(db):
    """Create a vote row directly — the unique constraint is a database concern,
    so nothing here should go through application validation."""

    def _make(user: User, post: Post) -> PostVote:
        return PostVote.objects.create(user=user, post=post)

    return _make
