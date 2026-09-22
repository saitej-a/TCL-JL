"""Views for devices, notifications, and preferences (Phase 6.2 — 07 §11)."""

from __future__ import annotations

from uuid import UUID

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerified
from apps.accounts.views import SpecErrorMixin
from apps.candidates.permissions import IsActive
from apps.notifications.models import Device, Notification, NotificationPreference
from apps.notifications.serializers import (
    DeviceSerializer,
    DeviceWriteSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)
from apps.notifications.services import register_device
from apps.notifications.throttles import (
    DeviceRegistrationThrottle,
    NotificationReadsThrottle,
)


class _DeviceNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self) -> None:
        super().__init__(
            {
                "error": {
                    "code": "device_not_found",
                    "message": "Device not found.",
                }
            }
        )


class _NotificationNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self) -> None:
        super().__init__(
            {
                "error": {
                    "code": "notification_not_found",
                    "message": "Notification not found.",
                }
            }
        )


class _InvalidIsRead(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self) -> None:
        super().__init__(
            {
                "error": {
                    "code": "invalid_is_read",
                    "message": "The 'is_read' filter must be 'true' or 'false'.",
                }
            }
        )


def _clean_uuid(value: str | UUID, kind: str) -> UUID:
    """Parse UUID or raise uniform 404 inside project envelope (F3 discipline)."""
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        if kind == "device":
            raise _DeviceNotFound() from exc
        if kind == "notification":
            raise _NotificationNotFound() from exc
        raise _DeviceNotFound() from exc


class NotificationErrorMixin(SpecErrorMixin):
    """Translate notifications app exceptions into the standard project envelope."""

    pass


class DeviceListCreateView(NotificationErrorMixin, ListCreateAPIView):
    """POST /api/v1/devices/ (register FCM token) and GET /api/v1/devices/ (list active)."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    pagination_class = PageNumberPagination

    def get_throttles(self):
        if self.request.method == "POST":
            return [DeviceRegistrationThrottle()]
        return [NotificationReadsThrottle()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DeviceWriteSerializer
        return DeviceSerializer

    def get_queryset(self):
        return Device.objects.filter(
            user=self.request.user,
            is_active=True,
        ).order_by("-last_seen_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device, _created = register_device(
            request.user,
            **serializer.validated_data,
        )
        read_serializer = DeviceSerializer(device)
        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class DeviceDetailView(NotificationErrorMixin, APIView):
    """DELETE /api/v1/devices/<str:pk>/ — soft revoke device (07 §11.6, D7)."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified]

    def delete(self, request, pk: str):
        device_id = _clean_uuid(pk, "device")
        device = Device.objects.filter(
            id=device_id,
            user=request.user,
            is_active=True,
        ).first()
        if not device:
            raise _DeviceNotFound()

        device.is_active = False
        device.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationPagination(PageNumberPagination):
    """Injects top-level unread_count into paginated notification list (06.2 discretion item)."""

    def get_paginated_response(self, data):
        user = getattr(self, "request", None) and self.request.user
        unread_count = (
            Notification.objects.unread_count_for(user) if user and user.is_authenticated else 0
        )
        return Response(
            {
                "count": self.page.paginator.count,
                "unread_count": unread_count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


class NotificationListView(NotificationErrorMixin, ListAPIView):
    """GET /api/v1/notifications/ — paginated list of recipient's notifications (07 §11.1)."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    throttle_classes = [NotificationReadsThrottle]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).order_by("-created_at")

        is_read_param = self.request.query_params.get("is_read")
        if is_read_param is not None:
            val = is_read_param.strip().lower()
            if val == "true":
                qs = qs.filter(is_read=True)
            elif val == "false":
                qs = qs.filter(is_read=False)
            else:
                raise _InvalidIsRead()
        return qs


class NotificationReadView(NotificationErrorMixin, APIView):
    """POST /api/v1/notifications/<str:pk>/read/ — mark single notification read (07 §11.2, R4)."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified]

    def post(self, request, pk: str):
        notif_id = _clean_uuid(pk, "notification")
        notif = Notification.objects.filter(
            id=notif_id,
            recipient=request.user,
        ).first()
        if not notif:
            raise _NotificationNotFound()

        notif.mark_as_read()
        return Response(
            {
                "id": str(notif.id),
                "is_read": notif.is_read,
                "read_at": notif.read_at,
            },
            status=status.HTTP_200_OK,
        )


class NotificationReadAllView(NotificationErrorMixin, APIView):
    """POST /api/v1/notifications/read-all/ — mark all unread notifications read (07 §11.3, D5)."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified]

    def post(self, request):
        now = timezone.now()
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True, read_at=now)
        return Response(
            {
                "updated_count": updated_count,
                "message": "All unread notifications marked as read.",
            },
            status=status.HTTP_200_OK,
        )


class NotificationPreferenceView(NotificationErrorMixin, APIView):
    """GET/PATCH /api/v1/notifications/preferences/ — user push preferences (07 §11.7, D13)."""

    permission_classes = [IsAuthenticated, IsActive, IsVerified]

    def get(self, request):
        pref = NotificationPreference.objects.get_or_create_for(request.user)
        serializer = NotificationPreferenceSerializer(pref)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        pref = NotificationPreference.objects.get_or_create_for(request.user)
        serializer = NotificationPreferenceSerializer(
            pref,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
