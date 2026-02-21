"""Admin configuration for accounts app."""

from django.contrib import admin

from .models import LoginLog


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    """Read-only admin view for login/logout events."""

    list_display = ("timestamp", "user", "event", "ip_address")
    list_filter = ("event", "timestamp", "user")
    search_fields = ("user__username", "user__email", "ip_address")
    ordering = ("-timestamp",)
    readonly_fields = ("user", "event", "timestamp", "ip_address", "user_agent")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
