"""Profile ownership permission (T3.5).

``/api/v1/profile/`` routes resolve the object from ``request.user``, so the
view-level ``IsAuthenticated + IsVerified`` gate is what actually protects the
surface. This class makes the object-level ownership discipline explicit and
unit-testable (T3.8), and is reusable if a lookup-based route ever appears.
"""

from rest_framework.permissions import BasePermission


class IsActive(BasePermission):
    """Admits active users only — ``force_authenticate`` and DRF's
    ``IsAuthenticated`` both pass for inactive rows, so eligibility is enforced
    explicitly (3.2 invariant: tombstoned/suspended users never own profiles)."""

    message = "Account is not active."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class IsProfileOwner(BasePermission):
    """Admits only requests whose user owns the target profile."""

    message = "You do not have permission to access this profile."

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        return bool(
            user and user.is_authenticated and obj.user_id is not None and obj.user_id == user.id
        )
