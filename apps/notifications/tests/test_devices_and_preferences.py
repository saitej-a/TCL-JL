"""`Device` token uniqueness, activity stamps, and lazy preferences (07 §3.2-§3.3).

Two ideas are load-bearing here:

* The FCM token is unique **in the database** (`fcm_token = TextField(unique=True)`),
  so 6.2's registration path can upsert by token instead of racing two inserts into
  duplicate rows.
* Preferences are created **lazily and explicitly** (`get_or_create_for`, R6). No
  `post_save` signal ships, so a freshly created user really has no row — proven by
  asserting the table is empty, not by reading the code.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications.models import Device, NotificationPreference

pytestmark = pytest.mark.django_db

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "0001_initial.py"


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


# --- Device -------------------------------------------------------------------


def test_device_defaults_match_the_spec(make_device):
    device = make_device()

    assert device.device_type == Device.DeviceType.WEB
    assert device.browser == "Chrome"  # factory-supplied; the field default is below
    assert device.is_active is True
    assert device.last_seen_at is not None
    assert device.created_at is not None
    assert device.updated_at is not None

    bare = make_device(browser="", device_type=Device.DeviceType.WEB)
    assert Device._meta.get_field("browser").default == ""
    assert Device._meta.get_field("is_active").default is True
    assert Device._meta.get_field("device_type").default == Device.DeviceType.WEB
    assert bare.is_active is True


def test_duplicate_fcm_token_is_rejected_by_the_database(make_user, make_device):
    """Uniqueness must come from the column, not from a serializer's validation —
    two concurrent registrations of the same token still cannot both land."""
    user = make_user()
    make_device(user, fcm_token="fcm-shared-token")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Device.objects.create(user=user, fcm_token="fcm-shared-token")

    assert Device.objects.filter(fcm_token="fcm-shared-token").count() == 1


def test_two_tokens_for_one_user_are_both_allowed(make_user, make_device):
    """Multi-device fan-out (07 §7.1) — the unique index is on the token, not the user."""
    user = make_user()
    make_device(user, fcm_token="fcm-laptop")
    make_device(user, fcm_token="fcm-phone")

    assert user.devices.count() == 2


def test_update_fields_excludes_last_seen_at_from_the_refresh(make_device):
    """R9's caveat, pinned: `auto_now` only fires for fields named in `update_fields`,
    so 6.2's token-refresh path must list `last_seen_at` explicitly if it wants the
    refresh stamp moved. A full `save()` moves it, as the spec intends."""
    device = make_device()
    stale = timezone.now() - timedelta(days=1)
    # `.update()` bypasses `auto_now` on purpose, so the stale value is real.
    Device.objects.filter(pk=device.pk).update(last_seen_at=stale)
    device.refresh_from_db()

    device.browser = "Firefox"
    device.save(update_fields=["browser"])
    device.refresh_from_db()
    assert device.last_seen_at == stale

    device.save()
    device.refresh_from_db()
    assert device.last_seen_at > stale
    assert device.browser == "Firefox"


def test_device_ordering_is_newest_seen_first(make_user, make_device):
    """R7: 6.2's device list reads newest-first, and the ordering is pinned now."""
    user = make_user()
    older = make_device(user)
    newer = make_device(user)
    Device.objects.filter(pk=older.pk).update(last_seen_at=timezone.now() - timedelta(hours=1))

    assert list(user.devices.all()) == [newer, older]


def test_device_index_and_token_uniqueness_are_in_the_migration():
    text = _migration_text()

    assert text.count("idx_device_user_active") == 1
    assert "fcm_token" in text
    assert "unique=True" in text


# --- NotificationPreference ---------------------------------------------------


def test_creating_a_user_creates_no_preference_row(make_user):
    """R6: no signal, no implicit row — the laziness is proven, not just intended."""
    make_user()

    assert NotificationPreference.objects.count() == 0


def test_get_or_create_for_is_idempotent(make_user):
    user = make_user()

    first, created_first = NotificationPreference.get_or_create_for(user)
    second, created_second = NotificationPreference.get_or_create_for(user)

    assert created_first is True
    assert created_second is False
    assert first.pk == second.pk
    assert NotificationPreference.objects.filter(user=user).count() == 1


def test_get_or_create_for_scopes_to_one_user_each(make_user):
    first_user, second_user = make_user(), make_user()

    first_pref, _ = NotificationPreference.get_or_create_for(first_user)
    second_pref, _ = NotificationPreference.get_or_create_for(second_user)

    assert first_pref.pk != second_pref.pk
    assert NotificationPreference.objects.count() == 2


def test_preferences_are_reachable_from_the_user(make_user):
    user = make_user()
    preference, _ = NotificationPreference.get_or_create_for(user)

    assert user.notification_preferences.pk == preference.pk


def test_a_duplicate_preference_row_is_rejected(make_user):
    """OneToOne is a database guarantee, so a second row cannot exist even if a caller
    bypasses `get_or_create_for`."""
    user = make_user()
    NotificationPreference.get_or_create_for(user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NotificationPreference.objects.create(user=user)

    assert NotificationPreference.objects.filter(user=user).count() == 1
