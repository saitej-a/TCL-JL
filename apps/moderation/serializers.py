"""Moderation serializers (Phase 8.1 — 04 §63–§65; Phase 8.2 — 04 §68–§70)."""

from rest_framework import serializers

from apps.moderation.models import Report
from apps.moderation.services import ACTIONS as services_actions


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


# --- Phase 8.2: moderation queue + review (04 §68–§69) -----------------------------


class ModerationReportSerializer(serializers.Serializer):
    """04 §68's list shape, plus description for triage context.

    Deliberate omissions (04 §63 "Do not expose moderator-only information",
    §14.5): reviewed_by, reviewed_at, moderator_notes, reporter email.
    """

    id = serializers.UUIDField(read_only=True)
    reason = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    post_id = serializers.UUIDField(read_only=True, allow_null=True)
    comment_id = serializers.UUIDField(read_only=True, allow_null=True)
    description = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class ReportReviewSerializer(serializers.Serializer):
    """POST /moderation/reports/{id}/review/ body (04 §69 + T8.7's five actions)."""

    action = serializers.ChoiceField(choices=services_actions)
    moderator_notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    duration_days = serializers.IntegerField(required=False, min_value=0, default=0)

    def validate_duration_days(self, value):
        if value and int(value) > 365:
            raise serializers.ValidationError("duration_days must be 365 or less.")
        return value


class BanRequestSerializer(serializers.Serializer):
    """POST /moderation/users/{id}/ban/ body (04 §70, T8.8).

    duration_days > 0 → temporary suspension (08 §6.1); 0/absent → permanent.
    """

    reason = serializers.ChoiceField(choices=Report.ReportReason.values)
    duration_days = serializers.IntegerField(required=False, min_value=0, default=0)

    def validate_duration_days(self, value):
        if value and int(value) > 365:
            raise serializers.ValidationError("duration_days must be 365 or less.")
        return value
