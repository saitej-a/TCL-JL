"""Notifications and device routes (Phase 6.2 — 07 §11).

Identifier segments are `<str:pk>` (F3 discipline) so malformed IDs
produce the JSON error envelope instead of Django's default 404 handler.
"""

from django.urls import path

from apps.notifications.views import (
    DeviceDetailView,
    DeviceListCreateView,
    NotificationListView,
    NotificationPreferenceView,
    NotificationReadAllView,
    NotificationReadView,
)

urlpatterns = [
    path("devices/", DeviceListCreateView.as_view(), name="device-list-create"),
    path("devices/<str:pk>/", DeviceDetailView.as_view(), name="device-detail"),
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "notifications/read-all/",
        NotificationReadAllView.as_view(),
        name="notification-read-all",
    ),
    path(
        "notifications/<str:pk>/read/",
        NotificationReadView.as_view(),
        name="notification-read",
    ),
    path(
        "notifications/preferences/",
        NotificationPreferenceView.as_view(),
        name="notification-preferences",
    ),
]
