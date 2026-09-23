"""Community admin (Phase 8.2 — T8.6; 08 §7's announcement lifecycle).

The publish action routes through `Announcement.publish()` rather than flipping
`is_published` in a bulk `update()`: `update()` would skip `published_at` and the
broadcast dispatch, leaving a "published" row that nobody was told about.
"""

from django.contrib import admin, messages

from apps.community.models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "is_published",
        "is_pinned",
        "published_at",
        "expires_at",
        "created_by",
    )
    list_filter = ("is_published", "is_pinned")
    search_fields = ("title", "body")
    readonly_fields = ("published_at", "created_at", "updated_at")
    actions = ("publish_selected",)

    @admin.action(description="Publish selected announcements (broadcasts to the community)")
    def publish_selected(self, request, queryset):
        published = 0
        for announcement in queryset:
            if announcement.publish():
                published += 1
        self.message_user(
            request,
            f"Published {published} announcement(s); already-published rows were left alone.",
            level=messages.SUCCESS,
        )
