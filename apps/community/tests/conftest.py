"""Shared fixtures for the community test suite (5.1 + 5.2).

Two post/comment factories on purpose, so a test's intent is visible: `make_post`
and `make_comment` go through the services (the real write path with its
validation), while `make_orm_post` / `make_orm_comment` write directly — needed by
constraint and flag tests that must bypass application validation to prove what
the *database* enforces.

The 5.2 API fixtures (`api`, `auth_api`, `staff_api`) build on the 5.1 factories:
`auth_api` returns the client *and* its user because most endpoint tests need
both (the client to call, the user to assert authorship against).
"""

import pytest
from rest_framework.test import APIClient

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
        # Overrides apply in BOTH branches — a caller asking for
        # `is_verified=False` or `is_staff=True` must get it even without an
        # explicit email (5.2's permission tests depend on this).
        defaults = dict(is_verified=True)
        defaults.update(overrides)
        if email is None:
            email = f"cm-user-{User.objects.count()}@example.com"
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


# --- 5.2 API fixtures --------------------------------------------------------


@pytest.fixture
def api(db, make_user):
    """An authenticated reader client (fresh verified user) — the common case.
    `client.user` exposes the reader for authorship assertions."""
    client = APIClient()
    user = make_user()
    client.force_authenticate(user=user)
    client.user = user
    return client


@pytest.fixture
def anon_api(db):
    """An unauthenticated client — for 401/permission tests."""
    return APIClient()


@pytest.fixture
def auth_api(make_user):
    """An authenticated, verified, active candidate client (+ its user).

    Builds a **fresh client each call** — `api` (the reader), `auth_api()`
    (an author), and a second `auth_api()` (an attacker) are three distinct
    identities, so multi-party tests can't alias each other.
    `is_staff=True` stands in for moderators (Phase 8 owns real roles).
    """

    def _make(email: str | None = None, *, is_staff: bool = False):
        client = APIClient()
        user = make_user(email, is_staff=is_staff)
        client.force_authenticate(user=user)
        return client, user

    return _make


@pytest.fixture
def staff_api(make_user):
    """A staff (moderator stand-in) client and its user — its own client."""

    def _make():
        client = APIClient()
        user = make_user(is_staff=True)
        client.force_authenticate(user=user)
        return client, user

    return _make
