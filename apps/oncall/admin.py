"""Admin configuration for the on-call duty application.

The audit trail is append-only in admin. Duty/segment edits here bypass
``services.apply_assignment`` (no audit row, no segment sync) — use the
calendar for real changes; segments are exposed read-mostly for
forensic corrections of closed weeks only.
"""

from django.contrib import admin

from .models import OnCallChange, OnCallDuty, OnCallSegment


@admin.register(OnCallDuty)
class OnCallDutyAdmin(admin.ModelAdmin):
    """Admin interface for on-call duty assignments.

    Prefer the calendar UI: direct edits here skip the coverage
    segments and the audit trail.
    """

    list_display = ["week_label", "user", "notes", "created_at"]
    list_filter = ["year"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "notes"]
    raw_id_fields = ["user"]


@admin.register(OnCallSegment)
class OnCallSegmentAdmin(admin.ModelAdmin):
    """Coverage segments — read-mostly, for forensic corrections."""

    list_display = ["__str__", "year", "week_number", "user", "start_at", "end_at"]
    list_filter = ["year"]
    search_fields = ["user__username", "user__first_name", "user__last_name"]
    raw_id_fields = ["user"]
    readonly_fields = ["created_at"]


@admin.register(OnCallChange)
class OnCallChangeAdmin(admin.ModelAdmin):
    """Append-only audit trail: viewable, never editable."""

    list_display = ["__str__", "from_user", "to_user", "changed_by", "changed_at", "effective_at"]
    list_filter = ["year"]
    search_fields = [
        "from_user__username",
        "to_user__username",
        "changed_by__username",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
