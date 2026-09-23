"""Moderation admin (Phase 8.2 — MOD-05, T8.9; 08 §9, §9.1).

The Admin is MOD-05's primary triage surface. Every bulk action delegates to
`moderation.services` — the same writers the REST review endpoint uses — so the
two surfaces cannot drift: a report resolved here gets the same
reviewed_by/reviewed_at/moderator_notes and emits the same §11.1 log event, and
a ban here dispatches the same idempotent sever task.

§14.1 discipline: no action ever hard-deletes content — removal is the
`is_deleted` flag. §9.1's two actions ship (`dismiss_reports`,
`soft_delete_and_resolve`) plus T8.7/MOD-05's remaining three (`lock_posts`,
`warn_users`, `ban_users`).
"""

from django.contrib import admin, messages

from apps.moderation import services
from apps.moderation.models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """08 §9.1's configuration: triage columns, filters, search, bulk actions."""

    list_display = (
        "id",
        "target_type",
        "reason",
        "status",
        "reporter",
        "created_at",
        "reviewed_by",
    )
    list_filter = ("status", "reason", "created_at")
    search_fields = ("reporter__email", "description", "post__title", "comment__body")
    readonly_fields = ("id", "reporter", "post", "comment", "created_at", "updated_at")
    raw_id_fields = ("post", "comment")
    list_select_related = ("reporter", "reviewed_by")
    actions = (
        "dismiss_reports",
        "soft_delete_and_resolve",
        "lock_posts",
        "warn_users",
        "ban_users",
    )

    @admin.display(description="Target")
    def target_type(self, obj):
        if obj.post_id:
            return "POST"
        if obj.comment_id:
            return "COMMENT"
        return "?"

    def _run_action(self, request, queryset, action: str, verb: str) -> None:
        """Apply one triage action to every still-PENDING report in `queryset`.

        Skip-and-report (§9.1's `queryset.update` shortcut would silently write
        reviewed_by on terminal reports and skip the action effects entirely, so
        each row goes through the service one at a time):
        - already-terminal reports are skipped and counted;
        - per-row service refusals (LOCK_POST on a comment report, a staff
          target) are reported, never swallowed.
        """
        resolved = 0
        skipped = 0
        failures: list[str] = []
        for report in queryset:
            if report.status != Report.ReportStatus.PENDING:
                skipped += 1
                continue
            try:
                services.resolve_report(report, request.user, action=action)
            except (services.InvalidReportTarget, services.ModerationTargetError) as exc:
                failures.append(f"{report.pk}: {exc}")
                continue
            resolved += 1

        parts = [f"{verb} {resolved} report(s)"]
        if skipped:
            parts.append(f"skipped {skipped} already-reviewed")
        if failures:
            parts.append("failed: " + "; ".join(failures))
        message = "; ".join(parts) + "."
        level = messages.ERROR if failures else (messages.SUCCESS if resolved else messages.WARNING)
        self.message_user(request, message, level=level)

    @admin.action(description="Dismiss selected reports (No violation)")
    def dismiss_reports(self, request, queryset):
        """§9.1 verbatim behavior, via the shared service (D4)."""
        self._run_action(request, queryset, "DISMISS", "Dismissed")

    @admin.action(description="Resolve reports and soft-delete reported content")
    def soft_delete_and_resolve(self, request, queryset):
        """§9.1's resolve + tombstone path; notifies each author (§4.2.2)."""
        self._run_action(request, queryset, "REMOVE_CONTENT", "Removed content and resolved")

    @admin.action(description="Lock the reported thread (post reports only)")
    def lock_posts(self, request, queryset):
        self._run_action(request, queryset, "LOCK_POST", "Locked threads for")

    @admin.action(description="Warn the content author")
    def warn_users(self, request, queryset):
        self._run_action(request, queryset, "WARN_USER", "Warned authors for")

    @admin.action(description="Ban the content author permanently")
    def ban_users(self, request, queryset):
        """Permanent ban (§6.1) through the single ban writer — never a bare
        ``is_active`` edit, which would skip the audit line and the severing."""
        self._run_action(request, queryset, "BAN_USER", "Banned authors for")
