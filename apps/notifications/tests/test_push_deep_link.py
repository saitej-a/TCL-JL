"""Deep-link integration over the real push chain (Phase 9.4, D2).

The whole 6.2 pipeline runs for real here — `create_notification` writes the row,
`send_push_notification` executes synchronously through `get_push_backend()` and
the genuine `WebPushBackend` — with only `pywebpush.webpush` stubbed at the
transport edge. What is proven: the browser-standards backend receives exactly
the payload the task assembled, and its `click_action` deep-links to the post
while the lock-screen text stays template-owned (T-6.2-03: zero comment-body
content, 07 §8's zero-PII rule).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from django.test import override_settings

from apps.notifications.models import Device, Notification
from apps.notifications.services import PUSH_TEXT_TEMPLATES, create_notification
from apps.notifications.tasks import send_push_notification

pytestmark = pytest.mark.django_db

WEBPUSH_SETTINGS = {
    "PUSH_BACKEND": "webpush",
    "VAPID_PUBLIC_KEY": "BPublicKeyMaterialForTests",
    "VAPID_PRIVATE_KEY": "PrivateKeyMaterialForTests",
    "VAPID_SUBJECT": "mailto:push@example.com",
}


@pytest.fixture
def captured_webpush(monkeypatch):
    """Stub only the network edge of pywebpush; everything in between is real."""
    import pywebpush

    calls: list[dict[str, Any]] = []

    def fake_webpush(subscription_info, **kwargs):
        calls.append({"subscription": subscription_info, **kwargs})
        return None

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    return calls


def _subscription(endpoint: str) -> str:
    return json.dumps(
        {
            "endpoint": endpoint,
            "keys": {"p256dh": "p256dh-key-material", "auth": "auth-secret"},
        }
    )


def test_comment_push_reaches_a_web_device_with_the_post_deep_link(
    make_user, make_post, make_device, captured_webpush
):
    """The done-when's backend half, asserted at the wire the browser would see."""
    secret_comment_body = "Chennai batch 1 was released on June 10th, check the portal."
    author = make_user()
    post = make_post(author=author, title="Has anyone from 2025 Digital received JL?")
    make_device(
        user=author,
        device_type=Device.DeviceType.WEB,
        fcm_token=_subscription("https://push.example.com/send/web-1"),
    )

    with override_settings(**WEBPUSH_SETTINGS):
        notification = create_notification(
            author,
            notification_type=Notification.NotificationType.COMMENT,
            title="New Discussion Reply",
            message=f'A comment mentions: "{secret_comment_body}"',
            post=post,
        )
        assert notification is not None
        send_push_notification.apply(args=[str(notification.id)]).get()

    assert len(captured_webpush.calls) == 1
    call = captured_webpush.calls[0]
    payload = json.loads(call["data"])

    # The subscription JSON travelled as the token, verbatim.
    assert call["subscription"]["endpoint"] == "https://push.example.com/send/web-1"

    # The deep link is the task's click_action, not a URL a backend invented.
    assert payload["data"]["click_action"] == f"/community/posts/{post.pk}"
    assert payload["data"]["notification_id"] == str(notification.id)
    assert payload["data"]["type"] == Notification.NotificationType.COMMENT

    # Lock-screen text is template-owned: the post title appears, the comment
    # body never does (07 §8's zero-PII rule, now proven on the browser path).
    template_title, _ = PUSH_TEXT_TEMPLATES[Notification.NotificationType.COMMENT]
    assert payload["title"] == template_title
    assert payload["body"] == f'Someone commented on your post: "{post.title}"'
    assert secret_comment_body not in call["data"]


def test_postless_push_deep_links_to_the_dashboard(make_user, make_device, captured_webpush):
    """A notification with no post routes its click to /dashboard (tasks.py rule)."""
    user = make_user()
    make_device(
        user=user,
        device_type=Device.DeviceType.WEB,
        fcm_token=_subscription("https://push.example.com/send/web-2"),
    )

    with override_settings(**WEBPUSH_SETTINGS):
        notification = create_notification(
            user,
            notification_type=Notification.NotificationType.TIMELINE_REMINDER,
            title="Timeline Reminder",
            message="It has been a while since you updated your timeline.",
        )
        assert notification is not None
        send_push_notification.apply(args=[str(notification.id)]).get()

    payload = json.loads(captured_webpush.calls[0]["data"])
    assert payload["data"]["click_action"] == "/dashboard"
    _, template_body = PUSH_TEXT_TEMPLATES[Notification.NotificationType.TIMELINE_REMINDER]
    assert payload["body"] == template_body


def test_a_gone_web_subscription_is_deactivated_not_retried(
    make_user, make_post, make_device, captured_webpush, monkeypatch
):
    """410 → failed_tokens → the task's stale-token deactivation fires unchanged."""
    import pywebpush
    from pywebpush import WebPushException

    author = make_user()
    post = make_post(author=author)
    dead = make_device(
        user=author,
        device_type=Device.DeviceType.WEB,
        fcm_token=_subscription("https://push.example.com/send/gone"),
    )

    def gone(subscription_info, **kwargs):
        raise WebPushException("gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr(pywebpush, "webpush", gone)

    with override_settings(**WEBPUSH_SETTINGS):
        notification = create_notification(
            author,
            notification_type=Notification.NotificationType.COMMENT,
            title="New Discussion Reply",
            message="x",
            post=post,
        )
        assert notification is not None
        send_push_notification.apply(args=[str(notification.id)]).get()

    dead.refresh_from_db()
    assert dead.is_active is False
