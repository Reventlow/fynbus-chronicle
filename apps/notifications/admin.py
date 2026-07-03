"""Admin configuration for notifications."""

from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Read-mostly admin for inspecting delivered notifications."""

    list_display = ["recipient", "message", "actor", "created_at", "read_at"]
    list_filter = ["read_at", "created_at"]
    search_fields = ["recipient__username", "message"]
    raw_id_fields = ["recipient", "actor"]
    readonly_fields = ["created_at"]
