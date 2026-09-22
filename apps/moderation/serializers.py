"""Moderation serializers (Phase 8.1 — 04 §63–§65)."""

from rest_framework import serializers

from apps.moderation.models import Report


class ReportWriteSerializer(serializers.Serializer):
    """Request body for POST /api/v1/reports/ — exactly one of post_id/comment_id."""

    post_id = serializers.UUIDField(required=False, write_only=True)
    comment_id = serializers.UUIDField(required=False, write_only=True)
    reason = serializers.ChoiceField(choices=Report.ReportReason.values)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, write_only=True
    )

    def validate(self, attrs):
        if bool(attrs.get("post_id")) == bool(attrs.get("comment_id")):
            raise serializers.ValidationError(
                "A report must target either a post or a comment, not both or neither."
            )
        return attrs
