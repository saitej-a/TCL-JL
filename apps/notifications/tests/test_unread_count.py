"""`NotificationManager.unread_count_for` — D6's seam for the dashboard badge.

4.2 D1 shipped `community.unread_notifications: 0` as an explicit placeholder and
named Phase 6 as its author; 6.1 ships the helper, 6.2 wires it. The properties that
matter are that it is *recipient-scoped*, *read-state-only*, and *index-shaped* — a
`COUNT` over the `(recipient, is_read)` prefix of `idx_notif_recip_read_created` with
no `ORDER BY` (R-5), because ordering would turn an index-only count into a sort.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.notifications.models import Notification, NotificationManager

pytestmark = pytest.mark.django_db


def test_notification_objects_is_the_custom_manager():
    assert isinstance(Notification.objects, NotificationManager)


def test_zero_for_a_user_with_no_notifications(make_user, make_notification):
    recipient = make_user()
    make_notification(make_user())  # someone else's notification

    assert Notification.objects.unread_count_for(recipient) == 0


def test_counts_only_the_recipients_unread_rows(make_user, make_notification):
    recipient, other = make_user(), make_user()
    make_notification(recipient)
    make_notification(recipient, is_read=True, read_at=timezone.now())  # read: excluded
    make_notification(other)

    assert Notification.objects.unread_count_for(recipient) == 1
    assert Notification.objects.unread_count_for(other) == 1


def test_marking_one_read_drops_the_count_by_exactly_one(make_user, make_notification):
    recipient = make_user()
    rows = [make_notification(recipient) for _ in range(3)]
    assert Notification.objects.unread_count_for(recipient) == 3

    assert rows[0].mark_as_read() is True

    assert Notification.objects.unread_count_for(recipient) == 2


def test_count_sql_is_a_count_with_no_ordering(make_user, make_notification):
    recipient = make_user()
    make_notification(recipient)

    with CaptureQueriesContext(connection) as queries:
        Notification.objects.unread_count_for(recipient)

    assert len(queries.captured_queries) == 1
    sql = queries.captured_queries[0]["sql"].upper()
    assert "COUNT(" in sql
    assert "ORDER BY" not in sql


def test_count_costs_exactly_one_query(make_user, make_notification, django_assert_num_queries):
    recipient = make_user()
    for _ in range(5):
        make_notification(recipient)

    with django_assert_num_queries(1):
        Notification.objects.unread_count_for(recipient)


def test_count_ignores_type_and_never_touches_read_rows(make_user, make_notification):
    """The counter is purely the read-state prefix: `type` is not part of the index
    and must not affect the number, and unread rows stay counted whatever their type."""
    recipient = make_user()
    for notification_type in Notification.NotificationType.values:
        make_notification(recipient, type=notification_type)

    assert Notification.objects.unread_count_for(recipient) == len(
        Notification.NotificationType.values
    )

    # A second recipient's read rows never leak into the first recipient's count.
    other = make_user()
    make_notification(other, is_read=True, read_at=timezone.now())

    assert Notification.objects.unread_count_for(other) == 0
    assert Notification.objects.unread_count_for(recipient) == len(
        Notification.NotificationType.values
    )
