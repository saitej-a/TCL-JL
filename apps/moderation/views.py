"""Moderation views (Phase 8.1 — 04 §63–§65, T8.2; Phase 8.2 — 04 §67–§70, T8.7).

8.1's candidate surface: thin view over `services.create_report`. 8.2's staff
surface: the moderation queue (§68), report review (§69), and ban/unban (§70) —
all thin translators over `services.resolve_report`/`ban_user`/`unban_user`, the
same writers the Django Admin actions call (no second implementation to drift).

The error envelope is the project-wide `{"error": {"code", "message"}}` body;
typed APIException subclasses translate service errors at the boundary
(community's `_DuplicateVote`/`_Locked` style).

Throttle: `throttle_scope` is declared ON THE VIEW, not only on the throttle
class — DRF's ScopedRateThrottle reads the scope from the view and a class-level
scope alone is inert (7.2 R1; the defect still live on community's write views).
"""

import uuid

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerified
from apps.candidates.permissions import IsActive
from apps.community.permissions import IsModerator
from apps.moderation import services
from apps.moderation.models import Report
from apps.moderation.serializers import (
    BanRequestSerializer,
    ModerationReportSerializer,
    ReportReviewSerializer,
    ReportWriteSerializer,
)
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


# --- Phase 8.2: staff triage surface (04 §67–§70) ----------------------------------

# 08 §4.1's severity weights, static per CONTEXT D6. The log2 velocity
# multiplier is a recorded divergence (the reviewer works the whole queue at
# MVP scale; the multiplier's per-target aggregation buys nothing there).
REPORT_SEVERITY_WEIGHTS = {
    "SCAM": 100,
    "PERSONAL_INFORMATION": 90,
    "HARASSMENT": 60,
    "MISINFORMATION": 50,
    "SPAM": 30,
    "ABUSIVE_CONTENT": 30,
    "OTHER": 10,
}


class _ModerationBadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str, message: str):
        super().__init__({"error": {"code": code, "message": message}})


class _ModerationNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, code: str, message: str):
        super().__init__({"error": {"code": code, "message": message}})


def _clean_uuid(raw: str) -> uuid.UUID | None:
    """Parse a path UUID, or None — routes use <str:...> so malformed ids reach
    the view and get the JSON envelope instead of a Django-level 404 (the F3
    lesson from community's routes)."""
    try:
        return uuid.UUID(str(raw))
    except (TypeError, ValueError, AttributeError):
        return None


def _severity_ordered_reports(queryset) -> list:
    """§4.1 ordering per D6: severity weight descending, then newest first.

    Two stable passes — datetime objects do not negate, and this keeps the
    comparison timezone-aware without conversion.
    """
    reports = list(queryset)
    reports.sort(key=lambda r: r.created_at, reverse=True)
    reports.sort(key=lambda r: REPORT_SEVERITY_WEIGHTS.get(r.reason, 0), reverse=True)
    return reports


class ModerationReportListView(APIView):
    """`GET /api/v1/moderation/reports/` (04 §68) — the staff queue.

    Severity-ordered per §4.1/D6 (SCAM 100 → OTHER 10, then newest-first).
    `?status=` is whitelist-validated (unknown → 400 `invalid_filter`, the 7.2
    filter-validation precedent; this also bounds the result space to the four
    statuses). Staff-only: IsModerator on top of the standard candidate stack.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]

    VALID_STATUSES = {choice for choice, _ in Report.ReportStatus.choices}

    def get(self, request):
        raw_status = request.query_params.get("status", "PENDING")
        raw_status = (raw_status or "PENDING").strip().upper()
        if raw_status not in self.VALID_STATUSES:
            raise _ModerationBadRequest(
                "invalid_filter",
                "Unknown status filter. Valid values: PENDING, REVIEWED, RESOLVED, DISMISSED.",
            )
        queryset = (
            Report.objects.filter(status=raw_status)
            .select_related("post", "comment")
            .only(
                "id",
                "reason",
                "status",
                "description",
                "created_at",
                "post_id",
                "comment_id",
                "post__title",
                "comment__body",
            )
        )
        reports = _severity_ordered_reports(queryset)

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(reports, request)
        serializer = ModerationReportSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ReportReviewView(APIView):
    """`POST /api/v1/moderation/reports/{id}/review/` (04 §69, T8.7).

    Executes one of the five actions through services.resolve_report. 200 for
    the synchronous actions; 202 for BAN_USER, whose session/device severing
    completes asynchronously via the idempotent sever task (D1).
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]

    def post(self, request, report_id):
        report_uuid = _clean_uuid(report_id)
        report = (
            Report.objects.select_related("post__author", "comment__author")
            .filter(id=report_uuid)
            .first()
            if report_uuid is not None
            else None
        )
        if report is None:
            raise _ModerationNotFound("report_not_found", "Report not found.")

        serializer = ReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        notes = serializer.validated_data.get("moderator_notes", "")
        duration_days = serializer.validated_data.get("duration_days", 0)

        try:
            services.resolve_report(
                report,
                request.user,
                action=action,
                moderator_notes=notes,
                duration_days=duration_days,
            )
        except services.InvalidReportTarget as exc:
            raise _ModerationBadRequest("invalid_action", str(exc)) from exc
        except services.ModerationTargetError as exc:
            raise _ModerationBadRequest("moderation_target_invalid", str(exc)) from exc

        if action == "BAN_USER":
            return Response(
                {
                    "id": report.id,
                    "status": report.status,
                    "action": action,
                    "detail": "enforcement scheduled",
                },
                status=status.HTTP_202_ACCEPTED,
            )
        return Response(
            {"id": report.id, "status": report.status, "action": action},
            status=status.HTTP_200_OK,
        )


class UserBanView(APIView):
    """`POST /api/v1/moderation/users/{id}/ban/` (04 §70, T8.8).

    The single REST ban entry: services.ban_user performs §6 step 1 and
    dispatches the idempotent sever task. 202 — enforcement completes async.
    The response carries only id/is_active/banned_until (04 §70: no private
    account data; is_staff/is_superuser are never writable here).
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]

    def post(self, request, user_id):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        target_uuid = _clean_uuid(user_id)
        target = User.objects.filter(id=target_uuid).first() if target_uuid is not None else None
        if target is None:
            raise _ModerationNotFound("user_not_found", "User not found.")

        serializer = BanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.ban_user(
                request.user,
                target,
                reason=serializer.validated_data["reason"],
                duration_days=serializer.validated_data.get("duration_days", 0),
            )
        except services.ModerationTargetError as exc:
            raise _ModerationBadRequest("moderation_target_invalid", str(exc)) from exc

        target.refresh_from_db()
        return Response(
            {
                "id": target.id,
                "is_active": target.is_active,
                "banned_until": target.banned_until,
                "detail": "enforcement scheduled",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class UserUnbanView(APIView):
    """`POST /api/v1/moderation/users/{id}/unban/` (04 §70). 200 — synchronous."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsModerator]

    def post(self, request, user_id):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        target_uuid = _clean_uuid(user_id)
        target = User.objects.filter(id=target_uuid).first() if target_uuid is not None else None
        if target is None:
            raise _ModerationNotFound("user_not_found", "User not found.")

        services.unban_user(request.user, target)
        target.refresh_from_db()
        return Response(
            {"id": target.id, "is_active": target.is_active, "banned_until": target.banned_until},
            status=status.HTTP_200_OK,
        )
