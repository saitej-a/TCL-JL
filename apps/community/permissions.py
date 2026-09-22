"""Community permissions (T5.4-T5.11; 5.2 P5-P8; 04 §37, §42, §44).

P6 inverts 4.2's rule deliberately: a foreign post **exists publicly** — every
authenticated candidate can read it — so editing someone else's content returns
403, not 404. 4.2's 404 exists to prevent enumerating *private* resources; that
rationale does not apply here.

P8 splits author-power from moderation: the author edits and deletes their own
content, but lock/pin is moderator control only — the author of a post cannot
lock their own thread against other candidates. 08 §38 is a Phase 8 concern;
the phase ships the permission so the view's contract is complete.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAuthorOrReadOnly(BasePermission):
    """Object-level author gate on posts and comments (04 §37/§44).

    Read is granted by the view's `IsAuthenticated` stack (P5: the community is
    verified-candidates-only). Writes require authorship → 403 for anyone else,
    including staff (moderators remove via the Phase 8 soft-delete path, they do
    not silently edit candidates' words).
    """

    message = {
        "error": {"code": "not_author", "message": "Only the author can modify this content."}
    }

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.author_id == request.user.id


class IsModerator(BasePermission):
    """Lock/pin control (04 §38, P8) — staff-only until Phase 8's roles exist."""

    message = {
        "error": {"code": "moderator_only", "message": "Only moderators can perform this action."}
    }

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class CommunityAccess(BasePermission):
    """P5's community gate in one name: active **and** verified.

    A plain BasePermission subclass — `IsActive`/`IsVerified` are independent
    BasePermission classes, so inheriting from both would keep only one
    `has_permission` via the MRO and silently drop the other check.
    """

    message = "Community access requires an active, verified account."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_verified)
