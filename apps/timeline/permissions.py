"""Timeline object-level ownership (T4.7; 06 §4.3.3, §4.2).

``IsTimelineOwner`` is the second of two independent IDOR layers. The first is
query scoping — every timeline queryset is filtered by ``candidate__user=request.user``
(06 §4.2's "never query models using raw client-supplied identifiers"), which
means a foreign UUID can never resolve in the first place. This class makes the
object-level rule explicit and unit-testable, so a mistake in either layer alone
is not a breach.
"""

from rest_framework.permissions import BasePermission


class IsTimelineOwner(BasePermission):
    """Restricts timeline access strictly to the candidate who owns the event."""

    message = "You do not have permission to access this timeline event."

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        candidate = getattr(obj, "candidate", None)
        return bool(
            user
            and user.is_authenticated
            and candidate is not None
            and candidate.user_id is not None
            and candidate.user_id == user.id
        )
