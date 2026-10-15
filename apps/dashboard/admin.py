"""Django Admin configuration for the dashboard application."""

from django.contrib import admin

from .models import StatisticsShareLink


@admin.register(StatisticsShareLink)
class StatisticsShareLinkAdmin(admin.ModelAdmin):
    """Share links for the statistics; created and revoked from the Deling page."""

    list_display = ["label", "created_by", "created_at", "expires_at", "revoked_at", "use_count", "last_used_at"]
    list_filter = ["revoked_at"]
    search_fields = ["label"]
    readonly_fields = ["token", "created_by", "created_at", "last_used_at", "use_count"]
