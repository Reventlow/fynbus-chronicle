from django.contrib import admin

from .models import TicketLink


@admin.register(TicketLink)
class TicketLinkAdmin(admin.ModelAdmin):
    """Deleting a link here removes it in Chronicle only; the note on the
    ticket in ServiceDesk stays."""

    list_display = ("sdp_id", "subject", "priority_item", "case", "created_by", "created_at", "note_added_at")
    search_fields = ("subject", "sdp_id")
    readonly_fields = ("sdp_id", "subject", "priority_item", "case", "created_by", "created_at",
                       "note_added_at", "note_error")

    def has_add_permission(self, request):
        return False
