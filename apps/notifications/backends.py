"""Push notification backends (Phase 6.2 — decisions D1 and D2).

Provides an abstract PushBackend seam decoupling notification task logic from
FCM SDK calls:
- SendResult: frozen dataclass tracking delivery counts and unregistered/stale tokens.
- PushBackend: ABC defining the send() interface.
- RecordingPushBackend: in-memory append-only test double (test/CI default).
- FirebasePushBackend: real production adapter calling firebase-admin messaging.
- get_push_backend(): resolves backend based on settings.PUSH_BACKEND and environment.
"""

from __future__ import annotations

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
    failed_tokens: tuple[str, ...]  # UnregisteredError / SenderIdMismatchError only


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


class RecordingPushBackend(PushBackend):
    """Test double recording all send() invocations in an in-memory list."""

    def __init__(self, result: SendResult | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result

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


def get_push_backend() -> PushBackend:
    """Resolve push backend according to settings and environment."""
    backend = getattr(settings, "PUSH_BACKEND", "auto")
    if backend == "recording":
        return RecordingPushBackend()
    if backend == "firebase":
        return FirebasePushBackend()
    if backend == "auto":
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or os.environ.get(
            "FIREBASE_CREDENTIALS_PATH", ""
        )
        google_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if (cred_path and os.path.exists(cred_path)) or (
            google_creds and os.path.exists(google_creds)
        ):
            return FirebasePushBackend()
        return RecordingPushBackend()
    raise ValueError(f"Unknown PUSH_BACKEND setting: {backend}")
