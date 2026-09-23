"""Django admin for the custom User (2.x base; Phase 8.2 adds suspension tooling).

Django's stock UserAdmin hardcodes ``username`` — this override re-homes every
form/list on ``email`` so staff can manage candidate accounts without surprises.

Phase 8.2 (MOD-06 / T8.9): `banned_until` is visible, and suspension goes
through the moderation *service* — a bare ``is_active`` toggle here would set the
flag without the §11.1 audit line and without dispatching the session/device
severing task, leaving a suspended account with live sessions.
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "is_staff", "is_active", "banned_until", "date_joined")
    list_filter = ("is_staff", "is_active")
    search_fields = ("email",)
    readonly_fields = ("last_login", "date_joined")
    actions = ("ban_selected_users", "unban_selected_users")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        # Suspension boundary (08 §6.1): NULL while banned = permanent; a future
        # timestamp is a temporary suspension that auto-reinstates.
        ("Moderation", {"fields": ("banned_until",)}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")

    def _moderation_service(self):
        """Lazy import: keeps admin autodiscovery free of a cross-app import."""
        from apps.moderation import services

        return services

    @admin.action(description="Suspend selected accounts (permanent, severs sessions)")
    def ban_selected_users(self, request, queryset):
        services = self._moderation_service()
        banned = 0
        refused: list[str] = []
        for user in queryset:
            if not user.is_active:
                continue  # already suspended — re-banning is a no-op for staff
            try:
                services.ban_user(request.user, user, reason="OTHER", duration_days=0)
            except services.ModerationTargetError as exc:
                refused.append(f"{user.email}: {exc}")
                continue
            banned += 1

        parts = [f"Suspended {banned} account(s)"]
        if refused:
            parts.append("refused: " + "; ".join(refused))
        self.message_user(
            request,
            "; ".join(parts) + ".",
            level=messages.ERROR if refused else messages.SUCCESS,
        )

    @admin.action(description="Reinstate selected accounts (devices stay revoked)")
    def unban_selected_users(self, request, queryset):
        services = self._moderation_service()
        active = 0
        for user in queryset:
            if user.is_active and user.banned_until is None:
                continue
            services.unban_user(request.user, user)
            active += 1
        self.message_user(request, f"Reinstated {active} account(s).", level=messages.SUCCESS)
