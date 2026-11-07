"""Admin: read-only views of the Planner connection and sync state.

The sealed token cache and sealed codes are never shown.
"""

from django.contrib import admin

from .models import (
    PendingSignIn,
    PlannerChange,
    PlannerConnection,
    PlannerLink,
    PlannerUserConnection,
    SyncState,
)


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
    list_display = ("created_at", "created_by", "for_user", "status", "message", "handled_at")
    exclude = ("sealed",)


@admin.register(SyncState)
class SyncStateAdmin(_ReadOnly):
    list_display = ("last_success_at", "last_attempt_at", "next_due_at", "last_error", "last_counts")


@admin.register(PlannerUserConnection)
class PlannerUserConnectionAdmin(_ReadOnly):
    list_display = ("user", "account_upn", "connected_at", "last_token_ok_at", "last_error")
    exclude = ("sealed_token_cache", "home_account_id")

    def has_delete_permission(self, request, obj=None):
        return True  # deleting forgets that person's tokens


@admin.register(PlannerChange)
class PlannerChangeAdmin(_ReadOnly):
    list_display = ("created_at", "user", "kind", "task_id", "status", "message", "handled_at")
    list_filter = ("status", "kind")


@admin.register(PlannerLink)
class PlannerLinkAdmin(_ReadOnly):
    """Deleting a link here removes it in Chronicle only; the label and the
    reference on the Planner card stay until removed there."""

    list_display = ("task_title", "priority_item", "case", "created_by", "created_at")
    search_fields = ("task_title", "task_id")

    def has_delete_permission(self, request, obj=None):
        return True
