"""Serializers for devices, notifications, and preferences (Phase 6.2 — 07 §11)."""

from __future__ import annotations

from rest_framework import serializers

from apps.notifications.models import Device, Notification, NotificationPreference


class DeviceWriteSerializer(serializers.ModelSerializer):
    """Write-only serializer for FCM device registration (07 §11.4).

    The fcm_token is write_only and NEVER rendered back in any response.
    """

    fcm_token = serializers.CharField(
        write_only=True,
        required=True,
        max_length=4096,
    )
    device_type = serializers.ChoiceField(
        choices=Device.DeviceType.choices,
        default=Device.DeviceType.WEB,
    )
    browser = serializers.CharField(
        max_length=64,
        required=False,
        default="",
        allow_blank=True,
    )

    class Meta:
        model = Device
        fields = (
            "id",
            "fcm_token",
            "device_type",
            "browser",
            "is_active",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = ("id", "is_active", "last_seen_at", "created_at")

    def validate_fcm_token(self, value: str) -> str:
        token = value.strip()
        if not token:
            raise serializers.ValidationError("fcm_token may not be blank.")
        if len(token) > 4096:
            raise serializers.ValidationError("fcm_token exceeds maximum length.")
        return token


class DeviceSerializer(serializers.ModelSerializer):
    """Read serializer for registered devices (07 §11.4/§11.5).

    The fcm_token is completely omitted to protect device secrets.
    """

    class Meta:
        model = Device
        fields = (
            "id",
            "device_type",
            "browser",
            "is_active",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    """Read serializer for in-app notifications (07 §11.1)."""

    post_id = serializers.UUIDField(source="post_id", allow_null=True, read_only=True)
    comment_id = serializers.UUIDField(
        source="comment_id",
        allow_null=True,
        read_only=True,
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "type",
            "title",
            "message",
            "is_read",
            "read_at",
            "post_id",
            "comment_id",
            "created_at",
        )
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for user notification and push preferences (07 §8, §11.7)."""

    notify_on_comments = serializers.BooleanField(required=False)
    notify_on_replies = serializers.BooleanField(required=False)
    notify_on_milestones = serializers.BooleanField(required=False)
    notify_on_announcements = serializers.BooleanField(required=False)
    notify_on_timeline = serializers.BooleanField(required=False)
    push_enabled = serializers.BooleanField(required=False)

    class Meta:
        model = NotificationPreference
        fields = (
            "notify_on_comments",
            "notify_on_replies",
            "notify_on_milestones",
            "notify_on_announcements",
            "notify_on_timeline",
            "push_enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
