"""Admin for themes + their schedules + banner messages."""

from django.contrib import admin

from .models import Theme, ThemeBannerMessage, ThemeSchedule


class ThemeScheduleInline(admin.TabularInline):
    model = ThemeSchedule
    extra = 1
    fields = ["start_date", "end_date", "recurs_annually", "label"]


class ThemeBannerMessageInline(admin.TabularInline):
    model = ThemeBannerMessage
    extra = 1
    fields = ["text", "is_active", "order", "notes"]
    ordering = ["order", "id"]


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = (
        "name", "slug", "is_active", "user_selectable",
        "schedules_count", "messages_count",
    )
    list_filter = ("is_active", "user_selectable")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ThemeScheduleInline, ThemeBannerMessageInline]

    @admin.display(description="Skeduler")
    def schedules_count(self, obj):
        return obj.schedules.count()

    @admin.display(description="Banner-beskeder")
    def messages_count(self, obj):
        return obj.banner_messages.filter(is_active=True).count()


@admin.register(ThemeSchedule)
class ThemeScheduleAdmin(admin.ModelAdmin):
    list_display = ("theme", "start_date", "end_date", "recurs_annually", "label")
    list_filter = ("theme", "recurs_annually")
    date_hierarchy = "start_date"
    autocomplete_fields = ["theme"]
    list_editable = ("recurs_annually",)


@admin.register(ThemeBannerMessage)
class ThemeBannerMessageAdmin(admin.ModelAdmin):
    list_display = ("theme", "text_preview", "is_active", "order")
    list_filter = ("theme", "is_active")
    search_fields = ("text", "notes")
    list_editable = ("is_active", "order")
    autocomplete_fields = ["theme"]

    @admin.display(description="Tekst")
    def text_preview(self, obj):
        return obj.text[:80] + ("…" if len(obj.text) > 80 else "")
