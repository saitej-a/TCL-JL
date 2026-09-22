"""Moderation views (Phase 8.1 — 04 §63–§65, T8.2).

Thin view over `services.create_report`. The error envelope is the project-wide
`{"error": {"code", "message"}}` body; typed APIException subclasses translate
service errors at the boundary (community's `_DuplicateVote`/`_Locked` style).

Throttle: `throttle_scope` is declared ON THE VIEW, not only on the throttle
class — DRF's ScopedRateThrottle reads the scope from the view and a class-level
scope alone is inert (7.2 R1; the defect still live on community's write views).
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerified
from apps.candidates.permissions import IsActive
from apps.moderation import services
from apps.moderation.serializers import ReportWriteSerializer
from apps.moderation.throttles import ReportRateThrottle


class _InvalidReport(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, code: str = "invalid_report"):
        super().__init__({"error": {"code": code, "message": message}})


class _DuplicateReport(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self):
        super().__init__(
            {
                "error": {
                    "code": "duplicate_report",
                    "message": "You already have a pending report for this content.",
                }
            }
        )


class ReportListCreateView(APIView):
    """`POST /api/v1/reports/` (04 §63–§65, T8.2-T8.3).

    Reporting requires authentication (04 §202). 201 returns 04 §64's shape
    `{id, status: PENDING, message}` — and nothing else: no target body text,
    no reporter email (T-08.1-02).
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    throttle_classes = [ReportRateThrottle]
    # The scope lives on the view (7.2 R1) — see module docstring.
    throttle_scope = ReportRateThrottle.scope

    def post(self, request):
        serializer = ReportWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report = services.create_report(
                request.user,
                post=serializer.validated_data.get("post_id"),
                comment=serializer.validated_data.get("comment_id"),
                reason=serializer.validated_data["reason"],
                description=serializer.validated_data.get("description", ""),
            )
        except services.InvalidReportTarget as exc:
            raise _InvalidReport(str(exc)) from exc
        except services.DuplicateReportError as exc:
            raise _DuplicateReport() from exc
        return Response(
            {
                "id": report.id,
                "status": report.status,
                "message": "Report submitted successfully.",
            },
            status=status.HTTP_201_CREATED,
        )
