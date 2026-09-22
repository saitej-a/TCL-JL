"""Timeline serializers (T4.4-T4.6; 04 §24-§27; 4.2 R4/D3).

``TimelineEventSerializer`` is the single output shape (a **superset** of 04
§24.1 and §25 — each spec example is a subset of these six fields).
``TimelineEventWriteSerializer`` is the only input path: it whitelists three
fields and nothing else.

Two fields are deliberately absent from the input surface:

* ``candidate`` — ownership comes from ``request.user``, never a request body
  (06 §4.5: a client-supplied ``user_id``/``candidate_id`` must never determine
  who owns a row).
* ``is_verified`` — a moderation/verification flag (Phase 8 tooling). Accepting
  it would open a vertical-escalation path (06 §4.4): a candidate could
  self-verify their own milestones. It stays read-only everywhere.

Sync behaviour (which events move ``current_status``) is 4.1's service concern;
this layer only validates shape and dates.
"""

from rest_framework import serializers

from apps.timeline.models import TimelineEvent
from apps.timeline.validators import HORIZON_CODE, validate_event_date, validate_present_or_past


class EventTypeField(serializers.ChoiceField):
    """ChoiceField whose invalid-choice failure carries the pinned
    ``invalid_event_type`` code (T4.5) instead of DRF's generic
    ``invalid_choice``."""

    default_error_messages = {"invalid_choice": "Unknown event type: {input}."}

    def to_internal_value(self, data):
        if data in self.choices:
            return str(data)
        self.fail("invalid_choice", input=data)


class TimelineEventSerializer(serializers.ModelSerializer):
    """Owner representation — 04 §24.1 / §25 response shape."""

    class Meta:
        model = TimelineEvent
        fields = [
            "id",
            "event_type",
            "event_date",
            "description",
            "is_verified",
            "created_at",
        ]
        read_only_fields = ["id", "event_type", "event_date", "is_verified", "created_at"]


class TimelineEventWriteSerializer(serializers.ModelSerializer):
    """POST/PATCH input — exactly the three candidate-writable fields."""

    event_type = EventTypeField(choices=TimelineEvent.EventType.choices)
    event_date = serializers.DateField(
        validators=[validate_event_date],
        error_messages={HORIZON_CODE: "event_date is outside the allowed range."},
    )

    class Meta:
        model = TimelineEvent
        fields = ["event_type", "event_date", "description"]

    def validate(self, attrs):
        """D3: resolve the *effective* type/date so a PATCH of only one of them
        is judged against the stored value of the other."""
        instance = self.instance
        effective_type = attrs.get("event_type") or getattr(instance, "event_type", None)
        effective_date = attrs.get("event_date") or getattr(instance, "event_date", None)
        if effective_type and effective_date:
            try:
                validate_present_or_past(effective_type, effective_date)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({"event_date": exc.detail}) from exc
        return attrs
