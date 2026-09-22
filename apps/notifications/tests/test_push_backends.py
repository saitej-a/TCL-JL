"""Unit tests for push backends (Phase 6.2 — decisions D1 and D2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.notifications.backends import (
    FirebasePushBackend,
    PushBackend,
    RecordingPushBackend,
    SendResult,
    get_push_backend,
)


def test_get_push_backend_explicit_recording():
    with override_settings(PUSH_BACKEND="recording"):
        backend = get_push_backend()
        assert isinstance(backend, RecordingPushBackend)


def test_get_push_backend_explicit_firebase():
    with override_settings(PUSH_BACKEND="firebase"):
        backend = get_push_backend()
        assert isinstance(backend, FirebasePushBackend)


def test_get_push_backend_auto_no_credentials(monkeypatch):
    monkeypatch.delenv("FIREBASE_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    with override_settings(PUSH_BACKEND="auto", FIREBASE_CREDENTIALS_PATH=""):
        backend = get_push_backend()
        assert isinstance(backend, RecordingPushBackend)


def test_get_push_backend_auto_with_credentials_file(tmp_path):
    cred_file = tmp_path / "firebase-creds.json"
    cred_file.write_text('{"type": "service_account"}')
    with override_settings(PUSH_BACKEND="auto", FIREBASE_CREDENTIALS_PATH=str(cred_file)):
        backend = get_push_backend()
        assert isinstance(backend, FirebasePushBackend)


def test_get_push_backend_unknown_setting_raises():
    with override_settings(PUSH_BACKEND="invalid_backend"):
        with pytest.raises(ValueError, match="Unknown PUSH_BACKEND setting"):
            get_push_backend()


def test_recording_push_backend_records_calls_and_defaults_success():
    backend = RecordingPushBackend()
    assert issubclass(RecordingPushBackend, PushBackend)
    assert backend.calls == []

    tokens = ["token_1", "token_2"]
    title = "Test Title"
    body = "Test Body"
    data = {"click_action": "/dashboard", "type": "COMMENT"}

    result = backend.send(tokens, title, body, data)

    assert isinstance(result, SendResult)
    assert result.success_count == 2
    assert result.failure_count == 0
    assert result.failed_tokens == ()
    assert len(backend.calls) == 1
    assert backend.calls[0] == {
        "tokens": ["token_1", "token_2"],
        "title": title,
        "body": body,
        "data": data,
    }


def test_recording_push_backend_configurable_result():
    configured_result = SendResult(
        success_count=1,
        failure_count=1,
        failed_tokens=("bad_token",),
    )
    backend = RecordingPushBackend(result=configured_result)

    result = backend.send(["bad_token", "good_token"], "T", "B", {})
    assert result == configured_result
    assert len(backend.calls) == 1


def test_firebase_push_backend_empty_tokens_no_op():
    backend = FirebasePushBackend()
    with patch("firebase_admin.messaging.send_each_for_multicast") as mock_send:
        result = backend.send([], "Title", "Body", {"click_action": "/dashboard"})
        assert result == SendResult(success_count=0, failure_count=0, failed_tokens=())
        mock_send.assert_not_called()


def test_firebase_push_backend_builds_exact_multicast_message():
    backend = FirebasePushBackend()
    mock_app = MagicMock()
    backend._get_app = MagicMock(return_value=mock_app)

    with patch("firebase_admin.messaging.send_each_for_multicast") as mock_send:
        mock_response = MagicMock()
        mock_response.success_count = 2
        mock_response.failure_count = 0
        mock_response.responses = [
            MagicMock(success=True),
            MagicMock(success=True),
        ]
        mock_send.return_value = mock_response

        tokens = ["token_a", "token_b"]
        title = "Post Title"
        body = "Someone replied"
        data = {"notification_id": "123", "click_action": "/community/posts/456"}

        result = backend.send(tokens, title, body, data)

        assert result == SendResult(success_count=2, failure_count=0, failed_tokens=())
        mock_send.assert_called_once()
        multicast_msg = mock_send.call_args[0][0]
        assert mock_send.call_args[1]["app"] == mock_app

        # Assert MulticastMessage fields
        assert multicast_msg.tokens == tokens
        assert multicast_msg.notification.title == title
        assert multicast_msg.notification.body == body
        assert multicast_msg.data == data

        # Assert WebpushConfig structure (07 §6.1)
        wp = multicast_msg.webpush
        assert wp.notification.title == title
        assert wp.notification.body == body
        assert wp.notification.icon == "/icons/icon-192x192.png"
        assert wp.notification.badge == "/icons/badge-72x72.png"
        assert wp.fcm_options.link == "/community/posts/456"
        assert wp.headers == {"Urgency": "high", "TTL": "86400"}


def test_firebase_push_backend_classifies_errors_and_handles_wholesale_failure():
    from firebase_admin import messaging

    backend = FirebasePushBackend()
    backend._get_app = MagicMock()

    with patch("firebase_admin.messaging.send_each_for_multicast") as mock_send:
        resp_unreg = MagicMock(
            success=False,
            exception=messaging.UnregisteredError("token unregistered"),
        )
        resp_sender = MagicMock(
            success=False,
            exception=messaging.SenderIdMismatchError("sender mismatch"),
        )
        resp_other = MagicMock(
            success=False,
            exception=Exception("temporary network error"),
        )
        resp_ok = MagicMock(success=True)

        mock_batch = MagicMock()
        mock_batch.success_count = 1
        mock_batch.failure_count = 3
        mock_batch.responses = [resp_unreg, resp_sender, resp_other, resp_ok]
        mock_send.return_value = mock_batch

        tokens = ["t_unreg", "t_sender", "t_other", "t_ok"]
        result = backend.send(tokens, "T", "B", {})

        assert result.success_count == 1
        assert result.failure_count == 3
        assert result.failed_tokens == ("t_unreg", "t_sender")

    # Test wholesale failure re-raises
    with patch(
        "firebase_admin.messaging.send_each_for_multicast",
        side_effect=RuntimeError("SDK died"),
    ):
        with pytest.raises(RuntimeError, match="SDK died"):
            backend.send(["t1"], "T", "B", {})
