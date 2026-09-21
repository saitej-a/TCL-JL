"""Reusable permission classes (06 §4.3 pattern).

``IsVerified`` is consumed by Phase 5 mutations (verified-only posting).
It ships now with unit tests so later phases wire it without rework;
no auth view in this phase restricts by it (unverified users may log in,
06 §2.6).
"""

from rest_framework.permissions import BasePermission


class IsVerified(BasePermission):
    """Admits authenticated users whose email is verified."""

    message = "Email verification required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_verified)
