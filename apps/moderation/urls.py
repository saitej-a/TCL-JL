"""Moderation routes (Phase 8.1: /api/v1/reports/; Phase 8.2: /api/v1/moderation/*).

Included from `config/urls.py` under the shared `/api/v1/` prefix (the 7.2
per-app-include pattern). Identifier segments are `<str:...>` — malformed UUIDs
reach the views and get the JSON `*_not_found` envelope instead of a Django-level
404 (community's F3 lesson).
"""

from django.urls import path

from apps.moderation.views import (
    ModerationReportListView,
    ReportListCreateView,
    ReportReviewView,
    UserBanView,
    UserUnbanView,
)

urlpatterns = [
    path("reports/", ReportListCreateView.as_view(), name="report-list-create"),
    path(
        "moderation/reports/",
        ModerationReportListView.as_view(),
        name="moderation-report-list",
    ),
    path(
        "moderation/reports/<str:report_id>/review/",
        ReportReviewView.as_view(),
        name="moderation-report-review",
    ),
    path("moderation/users/<str:user_id>/ban/", UserBanView.as_view(), name="moderation-user-ban"),
    path(
        "moderation/users/<str:user_id>/unban/",
        UserUnbanView.as_view(),
        name="moderation-user-unban",
    ),
]
