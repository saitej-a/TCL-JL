"""Throttles for notification and device registration endpoints (Phase 6.2 — 07 §10)."""

from rest_framework.throttling import UserRateThrottle


class DeviceRegistrationThrottle(UserRateThrottle):
    """Limit device registrations to 10/hour per user to mitigate token spray."""

    scope = "device_registration"


class NotificationReadsThrottle(UserRateThrottle):
    """Limit notification list reads to 60/min per user (pollable hot path)."""

    scope = "notifications_reads"
