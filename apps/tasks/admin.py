"""
Django Admin configuration for the tasks application.

Provides a rich admin interface for managing tasks with inline
editing of state changes, notes, and attachments.
"""

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from .models import Task, TaskNote, TaskNoteAttachment, TaskStateChange


class TaskStateChangeInline(admin.TabularInline):
    """Inline admin for task state change audit log."""

    model = TaskStateChange
    extra = 0
    readonly_fields = ["from_state", "to_state", "changed_by", "changed_at"]
    classes = ["collapse"]


class TaskNoteAttachmentInline(admin.TabularInline):
    """Inline admin for note attachments."""

    model = TaskNoteAttachment
    extra = 1
    classes = ["collapse"]


class TaskNoteInline(admin.StackedInline):
    """Inline admin for task notes."""

    model = TaskNote
    extra = 0
    classes = ["collapse"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Admin configuration for Task model.

    Features:
    - Colored status badges in list display
    - Inline state changes and notes
    - Filtering by status and dates
    """

    fieldsets = [
        (
            None,
            {
                "fields": ["title", "description"],
            },
        ),
        (
            "Status og datoer",
            {
                "fields": [("status", "planned_start", "planned_end")],
            },
        ),
        (
            "Tildeling",
            {
                "fields": ["approvers", "assigned_to"],
            },
        ),
        (
            "Metadata",
            {
                "fields": ["created_by", "created_at", "updated_at", "order"],
                "classes": ["collapse"],
            },
        ),
    ]

    list_display = [
        "title",
        "colored_status",
        "planned_start",
        "planned_end",
        "created_by",
        "updated_at",
    ]
    list_filter = ["status", "planned_start", "created_at"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_by", "created_at", "updated_at"]
    filter_horizontal = ["assigned_to"]
    inlines = [TaskStateChangeInline, TaskNoteInline]

    def colored_status(self, obj: Task) -> str:
        """Display task status as a colored badge."""
        colors = {
            Task.Status.TODO: "#6B635B",
            Task.Status.DOING: "#4A7C8F",
            Task.Status.PAUSED: "#B8860B",
            Task.Status.TESTING: "#7D8471",
            Task.Status.APPROVAL: "#8B6F8E",
            Task.Status.COMPLETE: "#5B7D5B",
        }
        color = colors.get(obj.status, "#6B635B")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    colored_status.short_description = "Status"
    colored_status.admin_order_field = "status"

    def save_model(
        self, request: HttpRequest, obj: Task, form, change: bool
    ) -> None:
        """Set created_by on new objects."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TaskNote)
class TaskNoteAdmin(admin.ModelAdmin):
    """Admin for viewing all task notes."""

    list_display = ["subject", "task", "author", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["subject", "text"]
    inlines = [TaskNoteAttachmentInline]


@admin.register(TaskStateChange)
class TaskStateChangeAdmin(admin.ModelAdmin):
    """Admin for viewing task state change history."""

    list_display = ["task", "from_state", "to_state", "changed_by", "changed_at"]
    list_filter = ["to_state", "changed_at"]
    search_fields = ["task__title"]
    readonly_fields = ["task", "from_state", "to_state", "changed_by", "changed_at"]
