from django.contrib import admin
from django.utils.html import format_html

from .models import PastedImage


@admin.register(PastedImage)
class PastedImageAdmin(admin.ModelAdmin):
    list_display = ("key", "preview", "width", "height", "uploaded_by", "created_at")
    readonly_fields = ("key", "content_type", "width", "height", "uploaded_by", "created_at", "preview")
    search_fields = ("key",)

    @admin.display(description="Billede")
    def preview(self, obj: PastedImage) -> str:
        return format_html('<img src="{}" style="max-height:60px;max-width:160px">', obj.get_absolute_url())
