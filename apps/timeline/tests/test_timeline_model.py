"""TimelineEvent model tests (T4.1/T4.2; 4.1 spec invariants)."""

from datetime import date
from pathlib import Path

import pytest

from apps.timeline.models import TimelineEvent

pytestmark = pytest.mark.django_db


def test_uuidv4_pk_auto_assigned(make_profile):
    event = TimelineEvent.objects.create(
        candidate=make_profile(), event_type="INTERVIEW", event_date=date(2026, 4, 23)
    )
    assert event.pk is not None
    assert event.pk.version == 4  # UUIDv4 per T4.1


def test_event_type_choices_exact_t41_set():
    assert TimelineEvent.EventType.values == [
        "INTERVIEW",
        "SELECTION",
        "OFFER_LETTER",
        "READINESS_SURVEY",
        "JOINING_LETTER",
        "JOINING_DATE",
        "JOINED",
        "OTHER",
    ]


def test_defaults(make_profile):
    event = TimelineEvent.objects.create(
        candidate=make_profile(), event_type="OTHER", event_date=date(2026, 1, 1)
    )
    assert event.is_verified is False
    assert event.description == ""


def test_cascade_deletes_events_with_profile(make_profile):
    profile = make_profile()
    TimelineEvent.objects.create(
        candidate=profile, event_type="INTERVIEW", event_date=date(2026, 4, 23)
    )
    assert TimelineEvent.objects.count() == 1
    profile.delete()  # 06 §4.2 step 4: private events die with the profile
    assert TimelineEvent.objects.count() == 0


def test_related_name(make_profile):
    profile = make_profile()
    TimelineEvent.objects.create(
        candidate=profile, event_type="JOINED", event_date=date(2026, 8, 1)
    )
    assert profile.timeline_events.count() == 1


def test_meta_ordering_newest_first(make_profile):
    profile = make_profile()
    TimelineEvent.objects.create(
        candidate=profile, event_type="INTERVIEW", event_date=date(2026, 4, 23)
    )
    TimelineEvent.objects.create(
        candidate=profile, event_type="OFFER_LETTER", event_date=date(2026, 5, 5)
    )
    assert list(profile.timeline_events.values_list("event_type", flat=True)) == [
        "OFFER_LETTER",
        "INTERVIEW",
    ]


def test_compound_indexes_on_model_meta():
    """T4.2 indexes declared on the model with pinned names/columns."""
    indexes = {idx.name: idx.fields for idx in TimelineEvent._meta.indexes}
    assert indexes["idx_event_candidate_date"] == ["candidate", "-event_date"]
    assert indexes["idx_event_type_date"] == ["event_type", "event_date"]


def test_compound_indexes_present_in_0001_migration():
    """The generated 0001_initial carries both indexes incl. descending date."""
    migration = (Path(__file__).resolve().parents[1] / "migrations" / "0001_initial.py").read_text()
    assert "idx_event_candidate_date" in migration
    assert "idx_event_type_date" in migration
    assert "'-event_date'" in migration  # descending order survived generation
