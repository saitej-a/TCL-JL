"""Moderation test fixtures (Phase 8.1; Phase 8.2 adds staff/device/client)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.community.models import Comment, Post
from apps.notifications.models import Device


@pytest.fixture
def api(db):
    """DRF test client (supports force_authenticate)."""
    return APIClient()


@pytest.fixture
def target_device(db):
    """An active FCM device owned by the ban target (sever-task assertions)."""
    from apps.accounts.models import User as UserModel

    user = UserModel.objects.filter(email="author@example.com").first()
    if user is None:
        user = UserModel.objects.create_user(
            "author@example.com", "Str0ng!Passw0rd", is_verified=True
        )
    return Device.objects.create(user=user, fcm_token="fcm-target-token", is_active=True)


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
