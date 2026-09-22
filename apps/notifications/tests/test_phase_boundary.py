"""Phase 6.2 boundary tests (replacing 6.1's retired scope test).

Proves the deliberate scope boundaries of Phase 6.2 (D15, D16, R1):
1. No Announcement model or import inside apps.notifications (D15).
2. broadcast_announcement is not implemented; route stays inert (D15).
3. No frontend JS / service workers, and no producer functions for dormant types (D16, R1).
"""

from pathlib import Path

import apps.notifications.models as notif_models
import apps.notifications.services as notif_services


def test_no_announcement_model_or_import_in_notifications():
    """D15: Announcement model belongs to community; notifications never defines/imports it."""
    assert not hasattr(notif_models, "Announcement")
    with open(notif_models.__file__, encoding="utf-8") as f:
        content = f.read()
    assert "class Announcement" not in content
    assert "import Announcement" not in content


def test_broadcast_announcement_task_is_not_implemented():
    """D15: Broadcast task for platform-wide announcements is deferred; no task ships in 6.2."""
    assert not hasattr(notif_services, "broadcast_announcement")
    assert not hasattr(notif_services, "broadcast_announcement_task")


def test_no_service_worker_or_frontend_js_in_repo_and_no_producer_functions_for_dormant_types():
    """D16 / R1: Repo is backend-only (no JS), and producer functions exist only for real events."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    sw_matches = list(repo_root.glob("**/firebase-messaging-sw.js"))
    assert len(sw_matches) == 0

    # Producer functions exist only for COMMENT, REPLY, and VOTE_MILESTONE (R1)
    assert hasattr(notif_services, "notify_comment_created")
    assert hasattr(notif_services, "maybe_notify_vote_milestone")
    assert not hasattr(notif_services, "notify_announcement_created")
    assert not hasattr(notif_services, "notify_moderation_event")
    assert not hasattr(notif_services, "notify_timeline_reminder")
