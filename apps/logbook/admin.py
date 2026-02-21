"""
Django Admin configuration for the logbook application.

Provides a rich admin interface for managing weekly logs with inline
editing of priority items, absences, and incidents. Includes export
actions for PDF, Markdown, and Email.
"""

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.utils.html import format_html

from .exports.email import send_weeklog_email
from .exports.markdown import generate_markdown
from .exports.pdf import generate_pdf
from .models import Absence, Incident, PriorityItem, WeekLog


class PriorityItemInline(admin.TabularInline):
    """Inline admin for priority items within a week log."""

    model = PriorityItem
    extra = 1
    fields = ["title", "priority", "status", "description", "notes"]
    classes = ["collapse"]

    def get_queryset(self, request: HttpRequest):
        """Order by manual order, then priority descending, then title."""
        return super().get_queryset(request).order_by("order", "-priority", "title")


class AbsenceInline(admin.TabularInline):
    """Inline admin for absences within a week log."""

    model = Absence
    extra = 1
    fields = ["staff_name", "absence_type", "start_date", "end_date", "notes"]
    classes = ["collapse"]


class IncidentInline(admin.StackedInline):
    """Inline admin for incidents within a week log."""

    model = Incident
    extra = 0
    fields = [
        ("title", "incident_type", "severity"),
        "description",
        ("occurred_at", "resolved"),
        "resolution",
    ]
    classes = ["collapse"]


@admin.register(WeekLog)
class WeekLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for WeekLog model.

    Features:
    - List display with key statistics
    - Inline editing of related items
    - Export actions (PDF, Markdown, Email)
    - Filtering and search
    """

    list_display = [
        "week_label",
        "helpdesk_stats_display",
        "priority_count",
        "incident_count",
        "created_at",
    ]
    list_filter = ["year"]
    search_fields = ["summary"]
    date_hierarchy = "created_at"
    ordering = ["-year", "-week_number"]
    readonly_fields = ["created_at", "updated_at", "created_by"]
    inlines = [PriorityItemInline, AbsenceInline, IncidentInline]
    actions = ["export_pdf", "export_markdown", "send_email"]

    fieldsets = [
        (
            None,
            {
                "fields": [("year", "week_number")],
            },
        ),
        (
            "Helpdesk statistik",
            {
                "fields": [
                    ("helpdesk_new", "helpdesk_closed", "helpdesk_open"),
                ],
            },
        ),
        (
            "Ugeoversigt",
            {
                "fields": ["summary"],
            },
        ),
        (
            "Metadata",
            {
                "fields": ["created_by", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def week_label(self, obj: WeekLog) -> str:
        """Display formatted week label."""
        return obj.week_label

    week_label.short_description = "Uge"
    week_label.admin_order_field = "week_number"

    def helpdesk_stats_display(self, obj: WeekLog) -> str:
        """Display helpdesk statistics with color coding."""
        delta = obj.helpdesk_delta
        if delta > 0:
            color = "#A65D57"  # terracotta for increase
            sign = "+"
        elif delta < 0:
            color = "#7D8471"  # sage for decrease
            sign = ""
        else:
            color = "#6B635B"  # neutral
            sign = ""

        return format_html(
            '<span title="Nye: {}, Lukkede: {}, Åbne: {}">'
            "Nye: {} | Lukkede: {} | "
            '<span style="color: {}">Δ {}{}</span>'
            "</span>",
            obj.helpdesk_new,
            obj.helpdesk_closed,
            obj.helpdesk_open,
            obj.helpdesk_new,
            obj.helpdesk_closed,
            color,
            sign,
            delta,
        )

    helpdesk_stats_display.short_description = "Helpdesk"

    def priority_count(self, obj: WeekLog) -> int:
        """Count of priority items."""
        return obj.priority_items.count()

    priority_count.short_description = "Opgaver"

    def incident_count(self, obj: WeekLog) -> str:
        """Count of incidents with severity indicator."""
        total = obj.incidents.count()
        critical = obj.incidents.filter(severity="critical").count()
        if critical > 0:
            return format_html(
                '{} <span style="color: #A65D57">({}!)</span>',
                total,
                critical,
            )
        return str(total)

    incident_count.short_description = "Hændelser"

    def save_model(
        self, request: HttpRequest, obj: WeekLog, form, change: bool
    ) -> None:
        """Set created_by on new objects."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Eksporter valgte ugelogs som PDF")
    def export_pdf(self, request: HttpRequest, queryset) -> HttpResponse:
        """Export selected week logs as PDF."""
        if queryset.count() == 1:
            weeklog = queryset.first()
            pdf_content = generate_pdf(weeklog)
            filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.pdf"

            response = HttpResponse(pdf_content, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        else:
            self.message_user(request, "Vælg kun én ugelog til PDF-eksport.", "warning")

    @admin.action(description="Eksporter valgte ugelogs som Markdown")
    def export_markdown(self, request: HttpRequest, queryset) -> HttpResponse:
        """Export selected week logs as Markdown."""
        if queryset.count() == 1:
            weeklog = queryset.first()
            md_content = generate_markdown(weeklog)
            filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.md"

            response = HttpResponse(md_content, content_type="text/markdown")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        else:
            self.message_user(
                request, "Vælg kun én ugelog til Markdown-eksport.", "warning"
            )

    @admin.action(description="Send valgte ugelogs som email")
    def send_email(self, request: HttpRequest, queryset) -> None:
        """Send selected week logs via email."""
        for weeklog in queryset:
            success, message = send_weeklog_email(
                weeklog, from_email=request.user.email
            )
            level = "success" if success else "error"
            self.message_user(request, f"{weeklog.week_label}: {message}", level)


@admin.register(PriorityItem)
class PriorityItemAdmin(admin.ModelAdmin):
    """Admin for viewing all priority items across weeks."""

    list_display = ["title", "weeklog", "priority", "status", "updated_at"]
    list_filter = ["priority", "status", "weeklog__year"]
    search_fields = ["title", "description"]
    list_editable = ["priority", "status"]
    ordering = ["-weeklog__year", "-weeklog__week_number", "-priority"]


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    """Admin for viewing all absences."""

    list_display = ["staff_name", "absence_type", "start_date", "end_date", "weeklog"]
    list_filter = ["absence_type", "weeklog__year"]
    search_fields = ["staff_name", "notes"]
    date_hierarchy = "start_date"


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    """Admin for viewing all incidents."""

    list_display = [
        "title",
        "incident_type",
        "severity",
        "occurred_at",
        "resolved",
        "weeklog",
    ]
    list_filter = ["severity", "incident_type", "resolved", "weeklog__year"]
    search_fields = ["title", "description", "resolution"]
    date_hierarchy = "occurred_at"
    list_editable = ["resolved"]
