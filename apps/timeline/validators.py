"""Timeline event validation (T4.5; 4.2 D3).

Two date rules, deliberately distinct:

* **Range** — every type shares one bounded horizon so typo'd years are rejected
  (04 T4.5 "cannot be arbitrarily in the distant future") while every
  real-world milestone stays recordable. `JOINING_DATE` is legitimately in the
  future: a candidate records an upcoming joining date.
* **JOINING_LETTER present-or-past** — a letter is *issued*, not planned, so a
  future date there is a data-entry error rather than a plan. That rule needs
  both fields, so it lives in the serializer's ``validate()``.
"""

from datetime import date, timedelta

from django.conf import settings
from rest_framework import serializers

from apps.timeline.models import TimelineEvent

# Absurd-past floor: no real recruitment milestone predates this.
EARLIEST_EVENT_DATE = date(2000, 1, 1)

#: Types that must not be dated in the future (D3): a letter is issued, not planned.
PRESENT_OR_PAST_TYPES = frozenset({TimelineEvent.EventType.JOINING_LETTER})

HORIZON_CODE = "event_date_out_of_range"
FUTURE_CODE = "event_date_future"


def future_horizon() -> date:
    """Last acceptable event_date. Reads the setting at call time so
    ``override_settings`` (tests) and ops changes apply without code edits."""
    days = getattr(settings, "TIMELINE_FUTURE_HORIZON_DAYS", 730)
    return date.today() + timedelta(days=int(days))


def validate_event_date(value: date) -> date:
    """Reject dates outside [EARLIEST_EVENT_DATE, today + horizon] (T4.5)."""
    latest = future_horizon()
    if value > latest:
        raise serializers.ValidationError(
            f"event_date cannot be more than {settings.TIMELINE_FUTURE_HORIZON_DAYS} "
            "days in the future.",
            code=HORIZON_CODE,
        )
    if value < EARLIEST_EVENT_DATE:
        raise serializers.ValidationError(
            f"event_date cannot be earlier than {EARLIEST_EVENT_DATE.isoformat()}.",
            code=HORIZON_CODE,
        )
    return value


def validate_present_or_past(event_type: str, event_date: date) -> None:
    """D3 carve-out: JOINING_LETTER may only be dated today or earlier."""
    if event_type in PRESENT_OR_PAST_TYPES and event_date > date.today():
        raise serializers.ValidationError(
            "A joining letter cannot be dated in the future.",
            code=FUTURE_CODE,
        )
