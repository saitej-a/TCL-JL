"""Moderation routes (Phase 8.1): /api/v1/reports/ (04 §63–§65).

Included from `config/urls.py` under the shared `/api/v1/` prefix (the 7.2
per-app-include pattern). Moderator triage routes are 8.2's; §67's moderation
API is deliberately absent here.
"""

from django.urls import path

from apps.moderation.views import ReportListCreateView

urlpatterns = [
    path("reports/", ReportListCreateView.as_view(), name="report-list-create"),
]
