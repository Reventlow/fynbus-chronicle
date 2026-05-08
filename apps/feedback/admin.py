"""Admin for feature requests."""

from django.contrib import admin
from django.utils.html import format_html

from .models import FeatureRequest


@admin.register(FeatureRequest)
class FeatureRequestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "importance_badge",
        "status_badge",
        "version_bump",
        "submitted_by",
        "created_at",
    )
    list_filter = ("status", "category", "importance", "triggers_version_bump")
    search_fields = ("title", "description", "resolution_notes")
    readonly_fields = ("submitted_by", "solved_by", "solved_at", "created_at", "updated_at")
    ordering = ("status", "order", "-created_at")
    fieldsets = (
        (None, {"fields": ("title", "description")}),
        ("Klassificering", {"fields": ("category", "importance", "triggers_version_bump")}),
        ("Status", {"fields": ("status", "order", "resolution_notes", "solved_by", "solved_at")}),
        ("Metadata", {"fields": ("submitted_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Vigtighed", ordering="importance")
    def importance_badge(self, obj):
        colors = {"critical": "#a33", "high": "#c80", "medium": "#888", "low": "#aaa"}
        return format_html(
            '<span style="background:{};color:white;padding:2px 7px;border-radius:4px;font-size:11px;">{}</span>',
            colors.get(obj.importance, "#888"),
            obj.get_importance_display(),
        )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {"open": "#286ed2", "in_progress": "#b48438", "solved": "#3a7"}
        return format_html(
            '<span style="background:{};color:white;padding:2px 7px;border-radius:4px;font-size:11px;">{}</span>',
            colors.get(obj.status, "#888"),
            obj.get_status_display(),
        )

    @admin.display(description="v++", boolean=True, ordering="triggers_version_bump")
    def version_bump(self, obj):
        return obj.triggers_version_bump
