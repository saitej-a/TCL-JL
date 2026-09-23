"""Ban protocol tests (Phase 8.2 — D1/D2/D3/D9; 08 §6, §6.1, §11.1)."""

import logging
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.moderation import services
from apps.moderation.tasks import auto_reinstate_users, sever_banned_user_sessions
from apps.notifications.models import Device

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture
def moderator(db):
    return User.objects.create_user("mod@example.com", PASSWORD, is_verified=True, is_staff=True)


@pytest.fixture
def target(db):
    return User.objects.create_user("banned@example.com", PASSWORD, is_verified=True)


@pytest.fixture
def target_device(target):
    return Device.objects.create(user=target, fcm_token="fcm-token-1", is_active=True)


def _issue_session(user) -> str:
    """Issue a refresh token and record it as outstanding (as login/refresh do)."""
    token = RefreshToken.for_user(user)
    token.outstand()
    return str(token)


class TestBanUser:
    def test_ban_sets_inactive_and_logs(self, moderator, target, caplog):
        with caplog.at_level(logging.INFO, logger="moderation"):
            services.ban_user(moderator, target, reason="SCAM")
        target.refresh_from_db()
        assert target.is_active is False
        assert target.banned_until is None  # permanent
        events = [r for r in caplog.records if getattr(r, "action", None) == "BAN_USER"]
        assert len(events) == 1
        assert "MODERATION_ACTION_TAKEN" in events[0].getMessage()
        assert events[0].moderator_id == str(moderator.pk)
        assert events[0].target_id == str(target.pk)
        assert events[0].reason == "SCAM"

    def test_sever_task_blacklists_tokens_and_deactivates_devices(
        self, moderator, target, target_device
    ):
        raw = _issue_session(target)
        services.ban_user(moderator, target, reason="SCAM")
        assert target_device.is_active is True  # dispatch is async (D1)

        result = sever_banned_user_sessions(str(target.pk))
        assert result == {"tokens": 1, "devices": 1}

        target.refresh_from_db()
        assert BlacklistedToken.objects.filter(token__user=target).exists()
        assert Device.objects.filter(user=target, is_active=True).count() == 0
        # Replaying the severed refresh token is refused.
        with pytest.raises(TokenError):
            RefreshToken(raw)

    def test_sever_task_is_idempotent(self, moderator, target, target_device):
        _issue_session(target)
        services.ban_user(moderator, target, reason="SCAM")
        first = sever_banned_user_sessions(str(target.pk))
        second = sever_banned_user_sessions(str(target.pk))
        assert first == {"tokens": 1, "devices": 1}
        assert second == {"tokens": 0, "devices": 0}

    def test_sever_task_survives_missing_user(self, db):
        result = sever_banned_user_sessions(str(uuid4()))
        assert result == {"tokens": 0, "devices": 0}

    def test_temporary_ban_sets_banned_until(self, moderator, target):
        before = timezone.now()
        services.ban_user(moderator, target, reason="HARASSMENT", duration_days=7)
        after = timezone.now()
        target.refresh_from_db()
        assert target.is_active is False
        assert before + timezone.timedelta(days=7) <= target.banned_until
        assert target.banned_until <= after + timezone.timedelta(days=7)

    def test_reban_refires_severing(self, moderator, target, target_device):
        services.ban_user(moderator, target, reason="SCAM")
        sever_banned_user_sessions(str(target.pk))
        # A banned account re-registered a device; re-banning re-severs (D2).
        Device.objects.create(user=target, fcm_token="fcm-token-2", is_active=True)
        services.ban_user(moderator, target, reason="SCAM")
        sever_banned_user_sessions(str(target.pk))
        assert Device.objects.filter(user=target, is_active=True).count() == 0

    def test_staff_member_refused(self, moderator):
        other_staff = User.objects.create_user(
            "staff2@example.com", PASSWORD, is_verified=True, is_staff=True
        )
        with pytest.raises(services.ModerationTargetError):
            services.ban_user(moderator, other_staff, reason="SCAM")
        other_staff.refresh_from_db()
        assert other_staff.is_active is True

    def test_self_ban_refused(self, moderator):
        with pytest.raises(services.ModerationTargetError):
            services.ban_user(moderator, moderator, reason="SCAM")
        assert moderator.is_active is True


class TestUnbanUser:
    def test_unban_reactivates_without_reviving_devices(self, moderator, target, target_device):
        _issue_session(target)
        services.ban_user(moderator, target, reason="SCAM", duration_days=7)
        sever_banned_user_sessions(str(target.pk))

        services.unban_user(moderator, target)

        target.refresh_from_db()
        assert target.is_active is True
        assert target.banned_until is None
        # D2: severing is one-way — devices stay deactivated, tokens stay blacklisted.
        assert Device.objects.filter(user=target, is_active=True).count() == 0
        assert BlacklistedToken.objects.filter(token__user=target).exists()

    def test_unban_of_active_user_is_a_clean_noop(self, moderator, target):
        services.unban_user(moderator, target)
        target.refresh_from_db()
        assert target.is_active is True


class TestAutoReinstate:
    def test_lapsed_temporary_ban_is_reinstated(self, moderator, target):
        target.is_active = False
        target.banned_until = timezone.now() - timezone.timedelta(minutes=1)
        target.save(update_fields=["is_active", "banned_until"])

        count = auto_reinstate_users()
        assert count == 1
        target.refresh_from_db()
        assert target.is_active is True
        assert target.banned_until is None

    def test_future_temporary_ban_survives(self, moderator, target):
        target.is_active = False
        target.banned_until = timezone.now() + timezone.timedelta(days=2)
        target.save(update_fields=["is_active", "banned_until"])

        assert auto_reinstate_users() == 0
        target.refresh_from_db()
        assert target.is_active is False

    def test_permanent_ban_is_never_reinstated(self, moderator, target):
        target.is_active = False
        target.banned_until = None
        target.save(update_fields=["is_active", "banned_until"])

        assert auto_reinstate_users() == 0
        target.refresh_from_db()
        assert target.is_active is False

    def test_reinstatement_is_logged(self, moderator, target, caplog):
        target.is_active = False
        target.banned_until = timezone.now() - timezone.timedelta(minutes=1)
        target.save(update_fields=["is_active", "banned_until"])
        with caplog.at_level(logging.INFO, logger="moderation"):
            auto_reinstate_users()
        events = [r for r in caplog.records if getattr(r, "action", None) == "AUTO_REINSTATE"]
        assert len(events) == 1
