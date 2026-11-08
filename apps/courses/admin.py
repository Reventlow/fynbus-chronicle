from django.contrib import admin

from .models import CourseFolder, CourseMaterial


class CourseMaterialInline(admin.TabularInline):
    model = CourseMaterial
    extra = 0
    fields = ("title", "kind", "original_name", "size", "url", "added_by", "added_at")
    readonly_fields = ("kind", "original_name", "size", "added_by", "added_at")


@admin.register(CourseFolder)
class CourseFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_by", "created_at", "updated_at")
    inlines = [CourseMaterialInline]


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "folder", "kind", "size", "added_at")
    list_filter = ("kind", "folder")
    search_fields = ("title", "description", "original_name", "url")
    readonly_fields = ("key", "file", "original_name", "size", "added_by", "added_at")

    def has_add_permission(self, request):
        return False  # files are uploaded from the Kursusmateriale page
