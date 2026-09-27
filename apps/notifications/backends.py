"""Push notification backends (Phase 6.2 — decisions D1 and D2).

Provides an abstract PushBackend seam decoupling notification task logic from
FCM SDK calls:
- SendResult: frozen dataclass tracking delivery counts and unregistered/stale tokens.
- PushBackend: ABC defining the send() interface.
- RecordingPushBackend: in-memory append-only test double (test/CI default).-	FirebasePushBackend: real production adapter calling firebase-admin messaging.
-	WebPushBackend: browser-standards Web Push (VAPID) adapter, 9.4 D2 — the WEB
	  device path, where the token column carries a subscription JSON rather than an
	  FCM id.
-	get_push_backend(): resolves backend based on settings.PUSH_BACKEND and environment.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.conf import settings

logger = logging.getLogger("notifications")

_firebase_app: Any = None


@dataclass(frozen=True)
class SendResult:
    """Outcome of a push dispatch batch."""

    success_count: int
    failure_count: int
    failed_tokens: tuple[str, ...] = ()  # UnregisteredError / SenderIdMismatchError only
    retryable_tokens: tuple[str, ...] = ()

    @property
    def invalid_tokens(self) -> tuple[str, ...]:
        return self.failed_tokens


class PushBackend(ABC):
    """Abstract interface for push notification delivery."""

    @abstractmethod
    def send(
        self,
        tokens: Sequence[str],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> SendResult:
        """Deliver push message to a list of device tokens."""
        raise NotImplementedError

    def send_multicast(
        self,
        tokens: Sequence[str],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> SendResult:
        """Alias for send() (07 §5.1)."""
        return self.send(tokens, title, body, data)


class RecordingPushBackend(PushBackend):
    """Test double recording all send() invocations in an in-memory list."""

    def __init__(self, result: SendResult | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result

    def clear(self) -> None:
        self.calls.clear()

    @property
    def sent_messages(self) -> list[dict[str, Any]]:
        return self.calls

    def send(
        self,
        tokens: Sequence[str],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> SendResult:
        tokens_list = list(tokens)
        self.calls.append(
            {
                "tokens": tokens_list,
                "title": title,
                "body": body,
                "data": dict(data),
            }
        )
        if self._result is not None:
            return self._result
        return SendResult(
            success_count=len(tokens_list),
            failure_count=0,
            failed_tokens=(),
        )


class FirebasePushBackend(PushBackend):
    """Production push backend backed by firebase-admin."""

    def __init__(self) -> None:
        self._app = None

    def _get_app(self) -> Any:
        global _firebase_app
        if _firebase_app is None:
            import firebase_admin
            from firebase_admin import credentials

            try:
                _firebase_app = firebase_admin.get_app()
            except ValueError:
                cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or os.environ.get(
                    "FIREBASE_CREDENTIALS_PATH", ""
                )
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    _firebase_app = firebase_admin.initialize_app(cred)
                else:
                    _firebase_app = firebase_admin.initialize_app()
        return _firebase_app

    def send(
        self,
        tokens: Sequence[str],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> SendResult:
        tokens_list = list(tokens)
        if not tokens_list:
            return SendResult(success_count=0, failure_count=0, failed_tokens=())

        from firebase_admin import messaging

        app = self._get_app()

        webpush_config = messaging.WebpushConfig(
            notification=messaging.WebpushNotification(
                title=title,
                body=body,
                icon="/icons/icon-192x192.png",
                badge="/icons/badge-72x72.png",
            ),
            fcm_options=messaging.WebpushFCMOptions(link=data.get("click_action", "/dashboard")),
            headers={
                "Urgency": "high",
                "TTL": "86400",
            },
        )

        multicast_msg = messaging.MulticastMessage(
            tokens=tokens_list,
            notification=messaging.Notification(title=title, body=body),
            data=data,
            webpush=webpush_config,
        )

        failed_tokens: list[str] = []

        try:
            response = messaging.send_each_for_multicast(multicast_msg, app=app)
            logger.info(
                "FCM batch delivered: %d success, %d failure out of %d tokens.",
                response.success_count,
                response.failure_count,
                len(tokens_list),
            )
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    exc = resp.exception
                    if isinstance(
                        exc,
                        (messaging.UnregisteredError, messaging.SenderIdMismatchError),
                    ):
                        failed_tokens.append(tokens_list[idx])
                    else:
                        logger.warning(
                            "FCM delivery error on token %s...: %s",
                            tokens_list[idx][:8],
                            exc,
                        )
            return SendResult(
                success_count=response.success_count,
                failure_count=response.failure_count,
                failed_tokens=tuple(failed_tokens),
            )
        except Exception as e:
            logger.error("Critical failure sending FCM multicast: %s", e, exc_info=True)
            raise


class WebPushBackend(PushBackend):
    """Web Push (RFC 8030) delivery for browser subscriptions (9.4 D2).

    The token argument is the **subscription JSON** a browser produced through
    `PushManager.subscribe()` — not an FCM id. 6.2's `Device.fcm_token` is a unique
    opaque-text column, so a WEB device stores the same object there without a
    migration (9.4 research R1), and the two token vocabularies never share a
    backend: FCM stays the explicit setting for Android/iOS paths.

    Failure classification mirrors FirebasePushBackend's SendResult contract:
    404/410 (and a token that is not a subscription at all) are permanent, so the
    task deactivates the device instead of retrying; transport, DNS and crypto
    errors are retryable, so the task's backoff handles them.

    VAPID credentials are read here so a misconfigured backend fails at
    construction. `get_push_backend()` refuses to build this class without keys,
    and a direct construction without them is an error rather than every push
    silently failing at send time.
    """

    DEFAULT_VAPID_SUBJECT = "mailto:no-reply@tcsjoiningtracker.local"

    def __init__(self) -> None:
        self._vapid_public_key = _setting_or_env("VAPID_PUBLIC_KEY")
        self._vapid_private_key = _setting_or_env("VAPID_PRIVATE_KEY")
        self._vapid_subject = (
            _setting_or_env("VAPID_SUBJECT") or self.DEFAULT_VAPID_SUBJECT
        )
        if not (self._vapid_public_key and self._vapid_private_key):
            raise ValueError(
                "WebPushBackend requires VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY; "
                "set them in the environment (.env in dev) or use PUSH_BACKEND=recording."
            )

    def send(
        self,
        tokens: Sequence[str],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> SendResult:
        """Deliver one Web Push message per subscription token.

        `send_multicast`'s base implementation loops back into here, matching the
        task's per-recipient call shape (it passes one recipient's devices at a
        time).
        """
        tokens_list = list(tokens)
        if not tokens_list:
            return SendResult(success_count=0, failure_count=0, failed_tokens=())

        # Lazy import: pywebpush pulls `cryptography`, and no non-webpush code path
        # (or test) should pay for it or require it to be installed.
        from pywebpush import WebPushException, webpush

        # The wire payload is exactly the 6.2 contract: template title/body plus the
        # deep-link `data`. No post or comment text ever enters it (T-6.2-03).
        payload = json.dumps({"title": title, "body": body, "data": dict(data)})

        success_count = 0
        failed_tokens: list[str] = []
        retryable_tokens: list[str] = []

        for token in tokens_list:
            try:
                subscription = json.loads(token)
            except (TypeError, ValueError):
                subscription = None
            if not isinstance(subscription, dict) or "endpoint" not in subscription:
                # A row that is not a subscription can never be delivered; treating
                # it as retryable would retry it forever.
                logger.warning("WEBPUSH_MALFORMED_SUBSCRIPTION: token is not a subscription object")
                failed_tokens.append(token)
                continue

            try:
                webpush(
                    subscription_info=subscription,
                    data=payload,
                    vapid_private_key=self._vapid_private_key,
                    vapid_claims={"sub": self._vapid_subject},
                )
                success_count += 1
            except WebPushException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code in (404, 410):
                    # The browser dropped the subscription (uninstalled, permission
                    # revoked, profile deleted): permanent, like FCM's 410.
                    logger.info("WEBPUSH_SUBSCRIPTION_GONE: status=%s", status_code)
                    failed_tokens.append(token)
                else:
                    logger.warning("WEBPUSH_DELIVERY_FAILED: status=%s %s", status_code, exc)
                    retryable_tokens.append(token)
            except Exception as exc:
                logger.warning("WEBPUSH_TRANSPORT_ERROR: %s", exc)
                retryable_tokens.append(token)

        return SendResult(
            success_count=success_count,
            failure_count=len(failed_tokens) + len(retryable_tokens),
            failed_tokens=tuple(failed_tokens),
            retryable_tokens=tuple(retryable_tokens),
        )


def _setting_or_env(name: str) -> str:
    """Read a push setting from Django settings, falling back to the environment.

    Mirrors the `FIREBASE_CREDENTIALS_PATH` pattern above: settings win, but an
    unset setting does not hide an exported variable.
    """
    return getattr(settings, name, "") or os.environ.get(name, "")


def vapid_keys_configured() -> bool:
    """Whether both VAPID halves are present, i.e. Web Push can be signed for."""
    return bool(_setting_or_env("VAPID_PUBLIC_KEY") and _setting_or_env("VAPID_PRIVATE_KEY"))


_recording_backend_instance: RecordingPushBackend | None = None


def get_recording_push_backend() -> RecordingPushBackend:
    """Return singleton instance of RecordingPushBackend for tests."""
    global _recording_backend_instance
    if _recording_backend_instance is None:
        _recording_backend_instance = RecordingPushBackend()
    return _recording_backend_instance


def get_push_backend() -> PushBackend:
    """Resolve push backend according to settings and environment.

    Resolution chain (9.4 D2 adds the third value): explicit `recording`,
    `firebase` or `webpush` wins; `auto` resolves to Web Push when VAPID keys are
    configured (the browser is this project's first-class client), otherwise to
    Firebase when credentials exist, otherwise to the recording double — which
    keeps the credential-free dev/CI posture 6.2 established.
    """
    backend = getattr(settings, "PUSH_BACKEND", "auto")
    if backend == "recording":
        return get_recording_push_backend()
    if backend == "firebase":
        return FirebasePushBackend()
    if backend == "webpush":
        return WebPushBackend()
    if backend == "auto":
        if vapid_keys_configured():
            return WebPushBackend()
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or os.environ.get(
            "FIREBASE_CREDENTIALS_PATH", ""
        )
        google_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if (cred_path and os.path.exists(cred_path)) or (
            google_creds and os.path.exists(google_creds)
        ):
            return FirebasePushBackend()
        return get_recording_push_backend()
    raise ValueError(f"Unknown PUSH_BACKEND setting: {backend}")
