"""Unit tests for the Web Push backend (Phase 9.4, D2).

`pywebpush.webpush` is stubbed for every test here — no test in this module may
reach a real push service. What is asserted is the *contract* the 6.2 seam
established: per-token SendResult classification, the zero-PII wire payload, and
the VAPID identity each call is signed with.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from django.test import override_settings
from pywebpush import WebPushException

from apps.notifications.backends import (
    FirebasePushBackend,
    RecordingPushBackend,
    SendResult,
    WebPushBackend,
    get_push_backend,
)

VAPID_SETTINGS = {
    "PUSH_BACKEND": "webpush",
    "VAPID_PUBLIC_KEY": "BPublicKeyMaterialForTests",
    "VAPID_PRIVATE_KEY": "PrivateKeyMaterialForTests",
    "VAPID_SUBJECT": "mailto:push@example.com",
}

ENDPOINT_OK = "https://push.example.com/send/ok"
ENDPOINT_GONE = "https://push.example.com/send/gone"
ENDPOINT_ERRORING = "https://push.example.com/send/erroring"
ENDPOINT_OFFLINE = "https://push.example.com/send/offline"


def _subscription(endpoint: str) -> str:
    """The JSON blob a browser stores in the token column (6.2 schema reuse)."""
    return json.dumps(
        {
            "endpoint": endpoint,
            "keys": {"p256dh": "p256dh-key-material", "auth": "auth-secret"},
        }
    )


@pytest.fixture(autouse=True)
def no_ambient_push_env(monkeypatch):
    """Keep resolution tests independent of whatever the developer exported."""
    for name in (
        "VAPID_PUBLIC_KEY",
        "VAPID_PRIVATE_KEY",
        "VAPID_SUBJECT",
        "FIREBASE_CREDENTIALS_PATH",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(name, raising=False)
    with override_settings(
        VAPID_PUBLIC_KEY="",
        VAPID_PRIVATE_KEY="",
        VAPID_SUBJECT="",
        FIREBASE_CREDENTIALS_PATH="",
    ):
        yield


@pytest.fixture
def captured_webpush(monkeypatch):
    """Replace `pywebpush.webpush` and record every call, keyed by endpoint."""
    import pywebpush

    calls: list[dict[str, Any]] = []
    failures: dict[str, Exception] = {}

    def fake_webpush(subscription_info, **kwargs):
        calls.append({"subscription": subscription_info, **kwargs})
        failure = failures.get(subscription_info["endpoint"])
        if failure is not None:
            raise failure
        return None

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    return SimpleNamespace(calls=calls, failures=failures)


def _web_push_exception(status_code: int) -> WebPushException:
    return WebPushException("push refused", response=SimpleNamespace(status_code=status_code))


# --- resolution chain --------------------------------------------------------


def test_explicit_webpush_setting_builds_the_backend():
    with override_settings(**VAPID_SETTINGS):
        assert isinstance(get_push_backend(), WebPushBackend)


def test_auto_prefers_webpush_once_vapid_keys_are_configured():
    """auto's new branch: VAPID configured means the browser path is live."""
    with override_settings(
        PUSH_BACKEND="auto",
        VAPID_PUBLIC_KEY="BPublicKeyMaterialForTests",
        VAPID_PRIVATE_KEY="PrivateKeyMaterialForTests",
    ):
        assert isinstance(get_push_backend(), WebPushBackend)


def test_auto_remains_credential_free_without_any_keys():
    """6.2's dev/CI posture survives: no keys, no crash, recording backend."""
    with override_settings(PUSH_BACKEND="auto"):
        assert isinstance(get_push_backend(), RecordingPushBackend)


def test_explicit_firebase_and_recording_are_untouched():
    with override_settings(PUSH_BACKEND="firebase"):
        assert isinstance(get_push_backend(), FirebasePushBackend)
    with override_settings(PUSH_BACKEND="recording"):
        assert isinstance(get_push_backend(), RecordingPushBackend)


@pytest.mark.parametrize(
    "overrides",
    (
        {"VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": "PrivateKeyMaterialForTests"},
        {"VAPID_PUBLIC_KEY": "BPublicKeyMaterialForTests", "VAPID_PRIVATE_KEY": ""},
        {"VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": ""},
    ),
)
def test_constructor_refuses_a_missing_vapid_half(overrides):
    """A half-configured sender must fail loudly, not on the first push."""
    settings = {
        **VAPID_SETTINGS,
        **overrides,
    }
    with override_settings(**settings):
        with pytest.raises(ValueError, match="VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY"):
            get_push_backend()


# --- send() contract --------------------------------------------------------


def test_send_classifies_every_outcome_per_token(captured_webpush):
    """410 → permanent (device deactivation), transport → retryable, junk → permanent."""
    captured_webpush.failures[ENDPOINT_GONE] = _web_push_exception(410)
    captured_webpush.failures[ENDPOINT_ERRORING] = _web_push_exception(503)
    captured_webpush.failures[ENDPOINT_OFFLINE] = ConnectionError("name resolution failed")

    tokens = [
        _subscription(ENDPOINT_OK),
        _subscription(ENDPOINT_GONE),
        _subscription(ENDPOINT_ERRORING),
        _subscription(ENDPOINT_OFFLINE),
        "not-json-at-all",
        json.dumps({"keys": {"p256dh": "x"}}),  # JSON, but not a subscription
    ]

    with override_settings(**VAPID_SETTINGS):
        result = WebPushBackend().send(tokens, "Discussion Trending", "Body text", {"a": "b"})

    assert isinstance(result, SendResult)
    assert result.success_count == 1
    assert result.failure_count == 5
    assert result.failed_tokens == (tokens[1], tokens[4], tokens[5])
    assert result.retryable_tokens == (tokens[2], tokens[3])
    assert result.invalid_tokens == result.failed_tokens
    assert len(captured_webpush.calls) == 4  # the two unusable rows never reached the wire


def test_send_of_no_tokens_touches_nothing(captured_webpush):
    with override_settings(**VAPID_SETTINGS):
        result = WebPushBackend().send([], "T", "B", {})

    assert result == SendResult(success_count=0, failure_count=0, failed_tokens=())
    assert captured_webpush.calls == []


def test_send_multicast_inherits_the_per_token_loop(captured_webpush):
    with override_settings(**VAPID_SETTINGS):
        result = WebPushBackend().send_multicast(
            [_subscription(ENDPOINT_OK)], "T", "B", {"click_action": "/dashboard"}
        )

    assert result.success_count == 1
    assert len(captured_webpush.calls) == 1


# --- wire payload -----------------------------------------------------------


def test_wire_payload_is_template_text_plus_deep_link_only(captured_webpush):
    """T-6.2-03 carries to the browser path: no post or comment text on the wire."""
    comment_body = "I received my joining letter yesterday, Chennai batch 1!"
    post_title = "Has anyone from 2025 Digital received JL?"

    with override_settings(**VAPID_SETTINGS):
        WebPushBackend().send(
            [_subscription(ENDPOINT_OK)],
            "New Discussion Reply",
            f'Someone commented on your post: "{post_title}"',
            {
                "notification_id": "9f0d1e6e-0000-4000-8000-000000000001",
                "type": "COMMENT",
                "click_action": "/community/posts/42",
            },
        )

    call = captured_webpush.calls[0]
    payload = json.loads(call["data"])

    assert set(payload) == {"title", "body", "data"}
    assert payload["title"] == "New Discussion Reply"
    assert payload["body"] == f'Someone commented on your post: "{post_title}"'
    assert payload["data"]["click_action"] == "/community/posts/42"
    assert payload["data"]["type"] == "COMMENT"
    assert comment_body not in call["data"]
    # The subscription is forwarded verbatim — pywebpush needs the whole object.
    assert call["subscription"]["endpoint"] == ENDPOINT_OK


def test_every_call_is_signed_with_the_configured_vapid_identity(captured_webpush):
    with override_settings(**VAPID_SETTINGS):
        WebPushBackend().send([_subscription(ENDPOINT_OK)], "T", "B", {})

    call = captured_webpush.calls[0]
    assert call["vapid_private_key"] == "PrivateKeyMaterialForTests"
    assert call["vapid_claims"] == {"sub": "mailto:push@example.com"}


def test_subject_falls_back_to_the_project_contact(captured_webpush):
    with override_settings(
        PUSH_BACKEND="webpush",
        VAPID_PUBLIC_KEY="BPublicKeyMaterialForTests",
        VAPID_PRIVATE_KEY="PrivateKeyMaterialForTests",
        VAPID_SUBJECT="",
    ):
        WebPushBackend().send([_subscription(ENDPOINT_OK)], "T", "B", {})

    assert captured_webpush.calls[0]["vapid_claims"] == {
        "sub": WebPushBackend.DEFAULT_VAPID_SUBJECT
    }
