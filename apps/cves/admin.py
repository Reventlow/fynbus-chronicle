"""Admin for CVEs, their links and comments."""

from django.contrib import admin

from .models import CVE, CVEAttachment, CVECase, CVEComment, CVELink


class CVELinkInline(admin.TabularInline):
    model = CVELink
    extra = 0
    fields = ("url", "label", "added_by", "added_at")
    readonly_fields = ("added_at",)


class CVECommentInline(admin.StackedInline):
    model = CVEComment
    extra = 0
    fields = ("kind", "text", "author", "created_at")
    readonly_fields = ("created_at",)


class CVEAttachmentInline(admin.TabularInline):
    model = CVEAttachment
    extra = 0
    fields = ["title", "original_name", "source", "tlp", "size", "uploaded_by", "uploaded_at"]
    readonly_fields = ["original_name", "size", "uploaded_by", "uploaded_at"]


@admin.register(CVE)
class CVEAdmin(admin.ModelAdmin):
    list_display = ("cve_id", "subject", "cvss", "severity", "state", "source", "updated_at")
    list_filter = ("state", "severity", "source")
    search_fields = ("cve_id", "subject")
    readonly_fields = ("updated_at", "solved_at", "solved_by")
    inlines = [CVEAttachmentInline, CVELinkInline, CVECommentInline]
    fieldsets = (
        (None, {"fields": ("cve_id", "subject", "cvss", "severity", "cvefeed_url")}),
        ("Status", {"fields": ("state", "case", "solved_at", "solved_by")}),
        ("Kilde", {"fields": ("source", "source_url")}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )


@admin.register(CVELink)
class CVELinkAdmin(admin.ModelAdmin):
    list_display = ("cve", "label", "url", "added_by", "added_at")
    search_fields = ("cve__cve_id", "label", "url")


@admin.register(CVEComment)
class CVECommentAdmin(admin.ModelAdmin):
    list_display = ("cve", "kind", "author", "created_at")
    list_filter = ("kind",)
    search_fields = ("cve__cve_id", "text")


@admin.register(CVEAttachment)
class CVEAttachmentAdmin(admin.ModelAdmin):
    list_display = ["display_title", "cve", "tlp", "source", "size", "uploaded_by", "uploaded_at"]
    list_filter = ["tlp"]
    search_fields = ["title", "original_name", "source", "cve__cve_id"]
    readonly_fields = ["key", "file", "original_name", "size", "uploaded_by", "uploaded_at"]


@admin.register(CVECase)
class CVECaseAdmin(admin.ModelAdmin):
    list_display = ("pk", "title", "source", "reference", "state", "resolution", "updated_at")
    list_filter = ("state", "resolution", "source")
    search_fields = ("title", "reference", "cves__cve_id")
    readonly_fields = ("created_at", "updated_at", "solved_at")
