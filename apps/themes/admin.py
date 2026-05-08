"""Admin for themes + their schedules."""

from django.contrib import admin

from .models import Theme, ThemeSchedule


class ThemeScheduleInline(admin.TabularInline):
    model = ThemeSchedule
    extra = 1
    fields = ["start_date", "end_date", "label"]


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "user_selectable", "schedules_count")
    list_filter = ("is_active", "user_selectable")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ThemeScheduleInline]

    @admin.display(description="Skeduler")
    def schedules_count(self, obj):
        return obj.schedules.count()


@admin.register(ThemeSchedule)
class ThemeScheduleAdmin(admin.ModelAdmin):
    list_display = ("theme", "start_date", "end_date", "label")
    list_filter = ("theme",)
    date_hierarchy = "start_date"
    autocomplete_fields = ["theme"]
