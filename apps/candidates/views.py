"""Profile API views (T3.4-T3.5; 3.2 D1-D4; 04 §19-§23).

Error bodies follow the 2.2 convention: field-validation failures render DRF's
field-error shape untouched; service-level rejections (409 duplicate, 400
illegal transition, 404 missing profile, 405 delete) render the project
``{"error": {code, message}}`` envelope through the accounts handler.
"""

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, MethodNotAllowed
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerified
from apps.accounts.views import SpecErrorMixin
from apps.candidates.models import CandidateProfile
from apps.candidates.permissions import IsActive
from apps.candidates.serializers import (
    CandidatePrivateSerializer,
    CandidateProfileCreateSerializer,
    CandidatePublicSerializer,
)
from apps.candidates.services import (
    InvalidTransitionError,
    ProfileAlreadyExistsError,
    create_profile,
    update_profile,
)


class _TransitionRejected(APIException):
    """Illegal status move (3.1 machine codes) rendered as the 400 envelope."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, code: str):
        super().__init__({"error": {"code": code, "message": message}})


class _ProfileExists(APIException):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self):
        super().__init__(
            {
                "error": {
                    "code": "profile_exists",
                    "message": "A candidate profile already exists for this account.",
                }
            }
        )


class _ProfileNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, message: str = "No candidate profile exists for this account."):
        super().__init__({"error": {"code": "profile_not_found", "message": message}})


def _method_not_allowed(method: str) -> MethodNotAllowed:
    """D4: profile removal belongs to account deletion (04 §22 preferred MVP)."""
    return MethodNotAllowed(
        method,
        detail={
            "error": {
                "code": "method_not_allowed",
                "message": (
                    f"{method} is not allowed here. To remove your profile, "
                    "use DELETE /api/v1/account/ (account deletion)."
                ),
            }
        },
    )


class ProfileView(SpecErrorMixin, APIView):
    """Self-service singleton at /api/v1/profile/ (04 §19-§22).

    Gated on active + verified users (3.1 D4 note); the object is always
    resolved from ``request.user``, so ownership is structural.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def handle_exception(self, exc):
        if isinstance(exc, InvalidTransitionError):
            exc = _TransitionRejected(str(exc), code=exc.code)
        elif isinstance(exc, ProfileAlreadyExistsError):
            exc = _ProfileExists()
        elif isinstance(exc, Http404):
            exc = _ProfileNotFound()
        return super().handle_exception(exc)

    def http_method_not_allowed(self, request, *args, **kwargs):
        raise _method_not_allowed(request.method)

    def _get_profile(self) -> CandidateProfile:
        profile = getattr(self.request.user, "candidate_profile", None)
        if profile is None:
            raise Http404
        return profile

    def get(self, request):
        return Response(CandidatePrivateSerializer(self._get_profile()).data)

    def post(self, request):
        if CandidateProfile.objects.filter(user=request.user).exists():
            raise _ProfileExists()
        serializer = CandidateProfileCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        body = request.data if isinstance(request.data, dict) else {}
        profile = create_profile(
            request.user,
            dict(serializer.validated_data),
            requested_status=body.get("current_status"),
        )
        return Response(CandidatePrivateSerializer(profile).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        profile = self._get_profile()
        serializer = CandidatePrivateSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        profile = update_profile(profile, dict(serializer.validated_data))
        return Response(CandidatePrivateSerializer(profile).data)


class PublicCandidateView(SpecErrorMixin, RetrieveAPIView):
    """GET /api/v1/candidates/{id}/ — community-safe 04 §23 shape only (D2).

    AllowAny is deliberate: the serializer renders exactly six public fields;
    PROF-04 redaction tests pin the boundary.
    """

    permission_classes = [AllowAny]
    queryset = CandidateProfile.objects.select_related("user")
    serializer_class = CandidatePublicSerializer

    def handle_exception(self, exc):
        if isinstance(exc, Http404):
            exc = _ProfileNotFound("Candidate profile not found.")
        return super().handle_exception(exc)
