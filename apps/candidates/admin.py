"""Minimal admin for CandidateProfile (dev convenience; triage tooling is T8.9)."""

from django.contrib import admin

from apps.candidates.models import CandidateProfile


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "batch", "hiring_type", "current_status", "public_identity_mode")
    list_filter = ("current_status", "public_identity_mode", "hiring_type", "batch")
    search_fields = ("user__email", "display_name")
