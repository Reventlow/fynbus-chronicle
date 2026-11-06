"""Admin: read-only views of the Planner connection and sync state.

The sealed token cache and sealed codes are never shown.
"""

from django.contrib import admin

from .models import PendingSignIn, PlannerConnection, SyncState


class _ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PlannerConnection)
class PlannerConnectionAdmin(_ReadOnly):
    list_display = ("account_upn", "connected_at", "connected_by", "last_token_ok_at", "last_error")
    exclude = ("sealed_token_cache", "home_account_id")


@admin.register(PendingSignIn)
class PendingSignInAdmin(_ReadOnly):
    list_display = ("created_at", "created_by", "status", "message", "handled_at")
    exclude = ("sealed",)


@admin.register(SyncState)
class SyncStateAdmin(_ReadOnly):
    list_display = ("last_success_at", "last_attempt_at", "next_due_at", "last_error", "last_counts")
