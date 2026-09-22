"""Model structure, vocabulary, defaults, and schema invariants (6.1 D1-D6, R1-R9).

These are the tests that encode *decisions* rather than fields:

* the type vocabulary is the 07 §3.1 **superset** (D1) — `10_MVP_TASKS.md` T6.1 lists
  six and omits `SYSTEM`, the spec wins, so the divergence is asserted instead of
  silently resolved;
* the index names are asserted from the model **and** from the generated migration
  (the 5.1 two-level pattern), because a declared index that never reaches the
  database is exactly the failure this phase must not ship;
* the constraint is asserted to use `condition=`, not the deprecated `check=` (R2);
* `Device.__str__` renders no token and no email (R3, T-6.1-01);
* no serializer/view/URL/task exists in 6.1 — the scope boundary is a test, not a note.
"""

import uuid
from pathlib import Path

import pytest
from django.db.utils import DataError

from apps.notifications.models import Device, Notification, NotificationPreference

pytestmark = pytest.mark.django_db

MIGRATION_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION = MIGRATION_DIR / "0001_initial.py"

EXPECTED_TYPES = {
    "COMMENT": "New Comment",
    "REPLY": "New Reply",
    "VOTE_MILESTONE": "Upvote Milestone",
    "ANNOUNCEMENT": "Announcement",
    "MODERATION": "Moderation Alert",
    "TIMELINE_REMINDER": "Timeline Reminder",
    "SYSTEM": "System Alert",
}
# T6.1's list — a documented subset of the spec vocabulary, not a competing one.
MVP_TASK_TYPES = {
    "COMMENT",
    "REPLY",
    "VOTE_MILESTONE",
    "ANNOUNCEMENT",
    "MODERATION",
    "TIMELINE_REMINDER",
}
EXPECTED_DEVICE_TYPES = {
    "WEB": "Web Browser",
    "ANDROID": "Android Web/PWA",
    "IOS": "iOS Web/PWA",
    "OTHER": "Other",
}
MVP_TASK_DEVICE_TYPES = {"WEB", "ANDROID", "IOS"}

INDEX_NAMES = {
    "idx_notif_recip_read_created",
    "idx_notif_recipient_created",
    "idx_device_user_active",
}

PREFERENCE_FLAGS = (
    "notify_on_comment",
    "notify_on_reply",
    "notify_on_vote_milestone",
    "notify_on_announcements",
    "notify_timeline_reminders",
    "push_enabled",
)


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


# --- identity, vocabulary, defaults -------------------------------------------


def test_uuid_v4_primary_keys_are_assigned(make_notification, make_device, make_user):
    preference, _ = NotificationPreference.get_or_create_for(make_user())

    for obj in (make_notification(), make_device(), preference):
        assert isinstance(obj.pk, uuid.UUID)
        assert obj.pk.version == 4, obj


def test_notification_type_is_the_full_spec_vocabulary():
    assert {value: str(label) for value, label in Notification.NotificationType.choices} == (
        EXPECTED_TYPES
    )
    # D1's deliberate divergence, asserted rather than implied: the task list is a
    # subset, so nothing is missing from the spec's seven.
    assert MVP_TASK_TYPES <= set(Notification.NotificationType.values)


def test_device_type_is_the_full_spec_vocabulary():
    assert {value: str(label) for value, label in Device.DeviceType.choices} == (
        EXPECTED_DEVICE_TYPES
    )
    assert MVP_TASK_DEVICE_TYPES <= set(Device.DeviceType.values)


def test_notification_defaults_match_the_spec(make_notification):
    notification = make_notification()

    assert notification.type == Notification.NotificationType.SYSTEM
    assert notification.is_read is False
    assert notification.read_at is None
    assert notification.post is None
    assert notification.comment is None
    assert notification.created_at is not None


def test_preference_flags_all_default_to_true(make_user):
    for flag in PREFERENCE_FLAGS:
        assert NotificationPreference._meta.get_field(flag).default is True, flag

    preference, _ = NotificationPreference.get_or_create_for(make_user())
    assert all(getattr(preference, flag) is True for flag in PREFERENCE_FLAGS)


# --- fields and relations -----------------------------------------------------


def test_title_max_length_is_enforced_by_the_column(make_user):
    """`title` is `CharField(255)` with no validator, so the limit lives in the column:
    an over-long write fails at the database rather than being silently truncated."""
    assert Notification._meta.get_field("title").max_length == 255

    recipient = make_user()
    Notification.objects.create(recipient=recipient, title="x" * 255, message="boundary is fine")

    with pytest.raises(DataError):
        Notification.objects.create(recipient=recipient, title="x" * 256, message="one too many")


def test_post_and_comment_are_nullable_contextual_references(
    make_notification, make_post, make_comment
):
    """03 §12: explicit nullable FKs, because SYSTEM / TIMELINE_REMINDER / MODERATION
    notifications legitimately have no community context."""
    assert Notification._meta.get_field("post").null is True
    assert Notification._meta.get_field("comment").null is True

    post = make_post()
    comment = make_comment(post)
    contextual = make_notification(post=post, comment=comment)

    assert contextual.post_id == post.id
    assert contextual.comment_id == comment.id
    assert make_notification().post_id is None


def test_related_names_match_the_notification_surface(
    make_user, make_notification, make_device, make_post, make_comment
):
    recipient = make_user()
    post = make_post()
    comment = make_comment(post)
    notification = make_notification(recipient, post=post, comment=comment)
    device = make_device(recipient)
    preference, _ = NotificationPreference.get_or_create_for(recipient)

    assert list(recipient.notifications.all()) == [notification]
    assert list(recipient.devices.all()) == [device]
    assert recipient.notification_preferences.pk == preference.pk
    assert list(post.notifications.all()) == [notification]
    assert list(comment.notifications.all()) == [notification]


def test_ordering_is_pinned_for_the_models_that_paginate(make_notification, make_device):
    """R7: 6.2's pagination must be stable, so the ordering is pinned before the
    endpoints exist — and it has to match the compound indexes' shape."""
    assert Notification._meta.ordering == ["-created_at"]
    assert Device._meta.ordering == ["-last_seen_at"]
    assert NotificationPreference._meta.ordering == []

    recipient = make_device().user
    first = make_notification(recipient, title="one")
    second = make_notification(recipient, title="two")
    third = make_notification(recipient, title="three")

    assert list(Notification.objects.all()) == [third, second, first]


# --- schema artifacts ---------------------------------------------------------


def test_indexes_declared_and_present_in_initial_migration():
    declared = {index.name for index in Notification._meta.indexes}
    declared |= {index.name for index in Device._meta.indexes}
    assert declared == INDEX_NAMES

    text = _migration_text()
    for name in INDEX_NAMES:
        assert f"name='{name}'" in text, name
    # The unread-count index must stay descending on created_at (R-5/D6).
    assert "'-created_at'" in text


def test_constraint_is_declared_with_condition_not_the_deprecated_check():
    names = [getattr(c, "name", None) for c in Notification._meta.constraints]
    assert names == ["notification_read_state"]

    text = _migration_text()
    assert text.count("'notification_read_state'") == 1
    assert "models.CheckConstraint(condition=" in text
    assert "check=" not in text  # R2: Django 5.2 deprecated the old spelling


def test_one_migration_creates_the_three_tables():
    """The phase's whole schema is one generated artifact — never hand-edited, and
    never carrying a `RunPython` (R-2: `--reuse-db` truncates, it does not re-migrate)."""
    migration_files = sorted(p.name for p in MIGRATION_DIR.glob("[0-9]*.py"))
    assert migration_files == ["0001_initial.py"]

    text = _migration_text()
    assert text.count("migrations.CreateModel(") == 3
    for model_name in ("Notification", "Device", "NotificationPreference"):
        assert f"name='{model_name}'" in text
    assert "RunPython" not in text
    assert "UUIDField(default=uuid.uuid4" in text


def test_no_api_surface_ships_in_6_1():
    """Scope boundary as a test: 6.1 is model-only, and 6.2/6.3 own every endpoint,
    task, and admin surface. A file appearing here would mean the phase overreached."""
    package = MIGRATION_DIR.parent
    for module in ("views.py", "serializers.py", "urls.py", "tasks.py", "admin.py", "services.py"):
        assert not (package / module).exists(), module


# --- behaviour that protects the user ----------------------------------------


def test_device_str_renders_no_token_and_no_email(make_user, make_device):
    """R3 / T-6.1-01: 07 §3.2 renders `user.email`; `__str__` reaches logs, admin lists,
    and error reports, so it renders device type + browser only."""
    user = make_user(email="leaky-identity@example.com")
    device = make_device(user, fcm_token="fcm-secret-token-value", browser="Brave")

    for rendered in (str(device), repr(device)):
        assert "fcm-secret-token-value" not in rendered
        assert "leaky-identity@example.com" not in rendered
    assert "Brave" in str(device)


def test_user_deletion_cascades_the_notification_domain(make_user, make_notification, make_device):
    """03 §19's CASCADE, and R8's dormancy: nothing in production deletes a User row
    (2.2 anonymizes instead), so this wiring is dormant — but it must still be real,
    or a genuinely deleted account would leave orphaned tokens behind."""
    user = make_user()
    make_notification(user)
    make_device(user)
    NotificationPreference.get_or_create_for(user)

    user.delete()

    assert Notification.objects.filter(recipient_id=user.pk).count() == 0
    assert Device.objects.filter(user_id=user.pk).count() == 0
    assert NotificationPreference.objects.filter(user_id=user.pk).count() == 0
