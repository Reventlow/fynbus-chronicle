"""Admin configuration for the on-call duty application."""

from django.contrib import admin

from .models import OnCallDuty


@admin.register(OnCallDuty)
class OnCallDutyAdmin(admin.ModelAdmin):
    """Admin interface for on-call duty assignments."""

    list_display = ["week_label", "user", "notes", "created_at"]
    list_filter = ["year"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "notes"]
    raw_id_fields = ["user"]
