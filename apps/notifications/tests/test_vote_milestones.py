"""Tests for post upvote milestone notifications and watermark deduplication (Phase 6.2 — D4)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.test import override_settings

from apps.notifications.models import Notification
from apps.notifications.services import maybe_notify_vote_milestone


@pytest.fixture(autouse=True)
def mock_tasks_delay(monkeypatch):
    mock_task = MagicMock()
    monkeypatch.setattr(
        "apps.notifications.services.send_push_notification",
        mock_task,
        raising=False,
    )
    return mock_task


def test_crossing_at_exactly_10_creates_milestone_row(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author, title="Offer Letter Released")

    notif = maybe_notify_vote_milestone(post, voter, previous_count=9, current_count=10)

    assert notif is not None
    assert notif.recipient == author
    assert notif.type == Notification.NotificationType.VOTE_MILESTONE
    assert notif.title == "Upvote Milestone Reached"
    assert notif.message == f"Your discussion '{post.title}' has reached 10 upvotes!"
    assert notif.post == post


def test_below_threshold_does_not_notify(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author)

    assert maybe_notify_vote_milestone(post, voter, previous_count=0, current_count=1) is None
    assert maybe_notify_vote_milestone(post, voter, previous_count=1, current_count=5) is None
    assert maybe_notify_vote_milestone(post, voter, previous_count=5, current_count=9) is None
    assert Notification.objects.count() == 0


def test_unvote_and_revote_across_same_threshold_suppressed_by_watermark(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author)

    # First crossing: 9 -> 10 creates milestone row (watermark = 0, index = 0, 0 >= 0: OK)
    notif1 = maybe_notify_vote_milestone(post, voter, previous_count=9, current_count=10)
    assert notif1 is not None
    assert Notification.objects.filter(post=post).count() == 1

    # Unvote drops back to 9. Voter or another peer revotes to 10.
    # Re-crossing: 9 -> 10 has index 0, but watermark is 1. 0 < 1 -> Suppressed!
    notif2 = maybe_notify_vote_milestone(post, voter, previous_count=9, current_count=10)
    assert notif2 is None
    assert Notification.objects.filter(post=post).count() == 1


def test_multi_threshold_jump_reports_highest_crossed(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author)

    # Viral jump: 9 -> 30 jumps both 10 and 25
    notif = maybe_notify_vote_milestone(post, voter, previous_count=9, current_count=30)

    assert notif is not None
    assert "25 upvotes!" in notif.message
    assert Notification.objects.filter(post=post).count() == 1


def test_author_self_crossing_suppressed_absolutely(make_user, make_post):
    author = make_user()
    post = make_post(author=author)

    # Author upvotes their own post to cross 10
    notif = maybe_notify_vote_milestone(post, author, previous_count=9, current_count=10)

    assert notif is None
    assert Notification.objects.count() == 0


def test_author_self_crossing_suppressed_then_peer_crossing_reports_next_threshold(
    make_user, make_post
):
    """Proves D4 caveat: author crossing 10 suppresses, threshold 10 is never reported."""
    author = make_user()
    peer1 = make_user()
    peer2 = make_user()
    post = make_post(author=author)

    # Author crosses 10 -> suppressed, 0 rows created
    notif_author = maybe_notify_vote_milestone(post, author, previous_count=9, current_count=10)
    assert notif_author is None
    assert Notification.objects.count() == 0

    # Peer votes 10 -> 11 (does not cross 10 or 25)
    notif_peer1 = maybe_notify_vote_milestone(post, peer1, previous_count=10, current_count=11)
    assert notif_peer1 is None
    assert Notification.objects.count() == 0

    # Peer votes 24 -> 25: crosses 25. Threshold index is 1, watermark is 0 (1 >= 0: OK)
    notif_peer2 = maybe_notify_vote_milestone(post, peer2, previous_count=24, current_count=25)
    assert notif_peer2 is not None
    assert "25 upvotes!" in notif_peer2.message
    assert Notification.objects.count() == 1


def test_thresholds_read_from_settings_at_call_time(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author)

    with override_settings(VOTE_MILESTONE_THRESHOLDS=[5, 15]):
        notif5 = maybe_notify_vote_milestone(post, voter, previous_count=4, current_count=5)
        assert notif5 is not None
        assert "5 upvotes!" in notif5.message

        notif15 = maybe_notify_vote_milestone(post, voter, previous_count=14, current_count=15)
        assert notif15 is not None
        assert "15 upvotes!" in notif15.message


def test_milestone_notification_metadata_and_ordering(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author, title="Discussion Post")

    notif = maybe_notify_vote_milestone(post, voter, previous_count=9, current_count=10)
    assert notif is not None
    assert notif.type == Notification.NotificationType.VOTE_MILESTONE
    assert notif.comment is None
    assert notif.is_read is False


def test_subsequent_threshold_crossings_each_notify(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author)

    n10 = maybe_notify_vote_milestone(post, voter, previous_count=9, current_count=10)
    assert n10 is not None
    assert "10 upvotes!" in n10.message

    n25 = maybe_notify_vote_milestone(post, voter, previous_count=24, current_count=25)
    assert n25 is not None
    assert "25 upvotes!" in n25.message

    n50 = maybe_notify_vote_milestone(post, voter, previous_count=49, current_count=50)
    assert n50 is not None
    assert "50 upvotes!" in n50.message

    assert Notification.objects.filter(post=post).count() == 3


def test_no_crossing_or_negative_delta_returns_none(make_user, make_post):
    author = make_user()
    voter = make_user()
    post = make_post(author=author)

    # Same count
    assert maybe_notify_vote_milestone(post, voter, previous_count=10, current_count=10) is None
    # Vote decrement
    assert maybe_notify_vote_milestone(post, voter, previous_count=15, current_count=12) is None
    assert Notification.objects.count() == 0
