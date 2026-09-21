"""Spec-shaped error envelopes for the auth surface (04 §14, 06 §7.3).

Attached per-view via ``accounts.views`` (global rollout deferred — plan):
- Authentication failures  → ``{"error": {"code", "message"}}``
- Throttled requests (429) → same envelope + RFC 6585 ``Retry-After`` header.
Every other exception falls through to DRF's default rendering untouched.
"""

from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def auth_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    view = context.get("view")
    if getattr(view, "spec_error_envelopes", False) is not True:
        return response

    if isinstance(exc, drf_exceptions.AuthenticationFailed) and response.status_code == 401:
        return Response(
            {
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid email or password.",
                }
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if isinstance(exc, drf_exceptions.Throttled) or response.status_code == 429:
        retry_after = getattr(exc, "wait", None)
        if retry_after is not None:
            response["Retry-After"] = int(retry_after) + 1
        response.data = {
            "error": {
                "code": "RATE_LIMITED",
                "message": "Request rate limit exceeded. Please wait before retrying.",
                "retry_after_seconds": int(retry_after) + 1 if retry_after is not None else None,
            }
        }
        return response

    return response
