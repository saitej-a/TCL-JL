"""Shared fixtures for the notification test suite (6.1).

Local on purpose: app-level conftests are not shared in this project, so this
package re-declares the `make_user` verified-user pattern the other apps use.

One factory per object, each writing **directly through the ORM**. There is no
service path in 6.1 (6.2 owns the endpoint-facing services), and more importantly
these tests have to prove what the *database* enforces: constraint and uniqueness
cases must bypass `full_clean()`, otherwise a passing test could just be Django's
application-level validation in disguise.
"""

import uuid

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.community.models import Comment, Post
from apps.notifications.models import Device, Notification

VALID_PASSWORD = "Correct Horse Battery 9!"


def _new_user(suffix: str) -> User:
    return User.objects.create_user(
        f"nt-{suffix}-{User.objects.count()}@example.com", VALID_PASSWORD, is_verified=True
    )


@pytest.fixture
def make_user(db):
    def _make(email: str | None = None, **overrides) -> User:
        # Overrides apply in BOTH branches, matching the community convention.
        defaults = dict(is_verified=True)
        defaults.update(overrides)
        if email is None:
            email = f"nt-user-{User.objects.count()}@example.com"
        return User.objects.create_user(email, VALID_PASSWORD, **defaults)

    return _make


@pytest.fixture
def make_notification(db):
    """Create a notification row straight through the ORM.

    `is_read=True` without `read_at` is deliberately expressible here — that is the
    illegal pair the constraint tests need to attempt.
    """

    def _make(recipient: User | None = None, **overrides) -> Notification:
        if recipient is None:
            recipient = _new_user("notif")
        defaults = dict(
            type=Notification.NotificationType.SYSTEM,
            title="Timeline reminder",
            message="Keeping your timeline current helps other candidates.",
        )
        defaults.update(overrides)
        return Notification.objects.create(recipient=recipient, **defaults)

    return _make


@pytest.fixture
def make_device(db):
    """Create a device row with a unique token unless the caller supplies one."""

    def _make(user: User | None = None, **overrides) -> Device:
        if user is None:
            user = _new_user("device")
        defaults = dict(
            fcm_token=f"fcm-{uuid.uuid4()}",
            device_type=Device.DeviceType.WEB,
            browser="Chrome",
        )
        defaults.update(overrides)
        return Device.objects.create(user=user, **defaults)

    return _make


@pytest.fixture
def make_post(db):
    """A community post, created by ORM — these tests exercise FK wiring, not the
    5.1 validation rules (which `community.services.create_post` already covers)."""

    def _make(author: User | None = None, **overrides) -> Post:
        if author is None:
            author = _new_user("post")
        defaults = dict(title="Joining letter updates?", body="Anyone heard back?", category="HELP")
        defaults.update(overrides)
        return Post.objects.create(author=author, **defaults)

    return _make


@pytest.fixture
def make_comment(db):
    def _make(post: Post, author: User | None = None, **overrides) -> Comment:
        if author is None:
            author = _new_user("comment")
        defaults = dict(body="Same here.")
        defaults.update(overrides)
        return Comment.objects.create(post=post, author=author, **defaults)

    return _make


# --- 6.2 API fixtures --------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_cache():
    """LocMemCache and recording backend isolation between test runs."""
    cache.clear()
    from apps.notifications.backends import RecordingPushBackend, get_push_backend

    backend = get_push_backend()
    if isinstance(backend, RecordingPushBackend):
        backend.clear()


@pytest.fixture
def api(db, make_user):
    """An authenticated reader client (fresh verified user)."""
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
    """Fresh authenticated client per call with independent user identity."""

    def _make(email: str | None = None, *, is_verified: bool = True, is_staff: bool = False):
        client = APIClient()
        user = make_user(email=email, is_verified=is_verified, is_staff=is_staff)
        client.force_authenticate(user=user)
        return client, user

    return _make
