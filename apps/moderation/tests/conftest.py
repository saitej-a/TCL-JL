"""Moderation test fixtures (Phase 8.1)."""

import pytest

from apps.accounts.models import User
from apps.community.models import Comment, Post


@pytest.fixture
def reporter(db):
    """A verified candidate who files reports."""
    return User.objects.create_user(
        email="reporter@example.com",
        password="Str0ng!Passw0rd",
        is_verified=True,
    )


@pytest.fixture
def other_reporter(db):
    """A second verified candidate — per-author isolation cases."""
    return User.objects.create_user(
        email="other.reporter@example.com",
        password="Str0ng!Passw0rd",
        is_verified=True,
    )


@pytest.fixture
def author(db):
    """A verified candidate who owns the reported content."""
    return User.objects.create_user(
        email="author@example.com",
        password="Str0ng!Passw0rd",
        is_verified=True,
    )


@pytest.fixture
def post(author):
    """A live post by the author — the default report target."""
    return Post.objects.create(
        author=author,
        title="Waiting for my joining letter",
        body="Anyone from the 2026 batch still waiting?",
        category="GENERAL",
    )


@pytest.fixture
def comment(post, author):
    """A live comment under the post — the alternate report target."""
    return Comment.objects.create(
        post=post,
        author=author,
        body="I am still waiting too.",
    )
