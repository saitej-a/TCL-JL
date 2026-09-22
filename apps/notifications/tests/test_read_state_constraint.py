"""`notification_read_state` — the phase's hard guarantee, proven at both layers (D5).

The distinction these tests defend: "read without a read timestamp" must be
impossible *at the database level*, not merely rejected by `clean()`. `clean()` is
only reached by `full_clean()` (forms, admin, explicit calls); `QuerySet.update()`,
`bulk_create()`, and raw SQL never touch it. So the two layers are proven
separately here rather than one being inferred from the other.

`IntegrityError` marks the connection as needing rollback, so every failing write is
wrapped in its own `transaction.atomic()` block — otherwise the assertion would
poison the surrounding test transaction.

The constraint is one-directional by design: `read_at` set while `is_read` is False
is legal, because the timestamp and the flag can legitimately arrive in that order.
"""

from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.notifications.models import READ_STATE_INCONSISTENT, Notification

pytestmark = pytest.mark.django_db

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "0001_initial.py"


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


# --- database layer -----------------------------------------------------------


def test_update_to_read_without_timestamp_is_rejected_by_the_database(make_notification):
    """R-1: the failure has to come from PostgreSQL, and the row must survive it."""
    notification = make_notification()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Notification.objects.filter(pk=notification.pk).update(is_read=True, read_at=None)

    notification.refresh_from_db()
    assert notification.is_read is False
    assert notification.read_at is None


def test_create_with_the_illegal_pair_is_rejected(make_user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Notification.objects.create(
                recipient=make_user(),
                is_read=True,
                read_at=None,
                title="Read but undated",
                message="Should never exist.",
            )

    assert Notification.objects.count() == 0


def test_bulk_create_of_the_illegal_pair_is_rejected(make_user):
    """Bulk writes skip per-row ORM validation entirely — an application-level check
    would not fire here, but the constraint still does."""
    recipient = make_user()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Notification.objects.bulk_create(
                [
                    Notification(
                        recipient=recipient,
                        is_read=True,
                        read_at=None,
                        title="Bulk illegal",
                        message="one",
                    ),
                    Notification(
                        recipient=recipient,
                        is_read=True,
                        read_at=None,
                        title="Bulk illegal",
                        message="two",
                    ),
                ]
            )

    assert Notification.objects.count() == 0


def test_the_three_legal_states_persist(make_notification):
    """`False/None` (fresh), `True/<ts>` (read), and `False/<ts>` (timestamp first) —
    the last one is why the constraint is one-directional."""
    unread = make_notification()
    read = make_notification(is_read=True, read_at=timezone.now())
    stamped_but_unread = make_notification(read_at=timezone.now())

    for row in (unread, read, stamped_but_unread):
        row.refresh_from_db()

    assert (unread.is_read, unread.read_at) == (False, None)
    assert read.is_read is True and read.read_at is not None
    assert stamped_but_unread.is_read is False and stamped_but_unread.read_at is not None
    assert Notification.objects.count() == 3


def test_the_constraint_is_declared_exactly_once_with_the_spec_name():
    names = [getattr(constraint, "name", None) for constraint in Notification._meta.constraints]

    assert names == ["notification_read_state"]


def test_migration_defines_the_constraint_and_never_patches_it_with_runpython():
    """R-2: `--reuse-db` truncates but never re-migrates, so a constraint created by
    `RunPython` would be silently absent from the test database."""
    text = _migration_text()

    assert text.count("'notification_read_state'") == 1
    assert "models.CheckConstraint(condition=" in text
    assert "RunPython" not in text


# --- application layer --------------------------------------------------------


def test_clean_raises_validation_error_with_the_stable_code(make_notification):
    """Distinct from the DB-layer test above: the application path gets a
    `ValidationError` (and a code 6.2 can translate into an HTTP 400), never a raw
    `IntegrityError` leaking out of the driver."""
    notification = make_notification()
    notification.is_read = True
    notification.read_at = None

    with pytest.raises(ValidationError) as excinfo:
        notification.clean()

    assert excinfo.value.error_dict["read_at"][0].code == READ_STATE_INCONSISTENT


def test_full_clean_surfaces_the_same_code(make_notification):
    notification = make_notification()
    notification.is_read = True
    notification.read_at = None

    with pytest.raises(ValidationError) as excinfo:
        notification.full_clean()

    assert excinfo.value.error_dict["read_at"][0].code == READ_STATE_INCONSISTENT


def test_clean_accepts_every_legal_state(make_notification):
    """The mirror must not be stricter than the constraint it mirrors."""
    for is_read, read_at in ((False, None), (True, timezone.now()), (False, timezone.now())):
        notification = make_notification(is_read=is_read, read_at=read_at)
        notification.clean()  # does not raise


# --- the sanctioned writer ----------------------------------------------------


def test_mark_as_read_writes_both_columns_in_a_single_update(make_notification):
    notification = make_notification()

    with CaptureQueriesContext(connection) as queries:
        flipped = notification.mark_as_read()

    updates = [q["sql"] for q in queries.captured_queries if q["sql"].lstrip().startswith("UPDATE")]
    assert flipped is True
    assert len(updates) == 1
    # Both columns in one statement — the pair can never disagree mid-transaction.
    assert "is_read" in updates[0]
    assert "read_at" in updates[0]

    notification.refresh_from_db()
    assert notification.is_read is True
    assert notification.read_at is not None


def test_mark_as_read_is_idempotent(make_notification):
    notification = make_notification()
    assert notification.mark_as_read() is True
    notification.refresh_from_db()
    first_read_at = notification.read_at

    assert notification.mark_as_read() is False

    notification.refresh_from_db()
    assert notification.read_at == first_read_at


def test_marked_notifications_satisfy_the_constraint(make_notification):
    """The two layers agree: what `mark_as_read()` writes is what the database allows,
    and the application mirror accepts the same row afterwards."""
    notification = make_notification()

    notification.mark_as_read()

    notification.refresh_from_db()
    notification.clean()  # does not raise
    assert Notification.objects.get(pk=notification.pk).read_at is not None
