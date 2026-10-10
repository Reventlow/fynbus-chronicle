from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_public", "created_by", "created_at", "updated_at")
    list_filter = ("is_public",)
    search_fields = ("title", "slug", "description")
    readonly_fields = ("public_token", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("title",)}
