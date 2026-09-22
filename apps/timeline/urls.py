"""Timeline & dashboard routes (Phase 4.2): /api/v1/timeline/ + /api/v1/dashboard/.

The dashboard lives here (4.2 R2) because 04 §84's layout defines four domain
apps and no dashboard app — it is a read-only aggregation route over the
timeline and profile domains, not a domain of its own.
"""

from django.urls import path

from apps.timeline.views import (
    DashboardView,
    TimelineEventDetailView,
    TimelineEventListCreateView,
)

urlpatterns = [
    path("timeline/", TimelineEventListCreateView.as_view(), name="timeline-list"),
    path(
        "timeline/<uuid:pk>/",
        TimelineEventDetailView.as_view(),
        name="timeline-detail",
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
]
