"""
Views for the logbook application.

Provides views for WeekLog CRUD operations and HTMX partials
for inline editing of priority items, absences, and incidents.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .exports.email import send_weeklog_email
from .exports.html import generate_html
from .exports.markdown import generate_markdown
from .exports.pdf import generate_pdf
from .forms import AbsenceForm, IncidentForm, PriorityItemForm, WeekLogForm
from .models import Absence, Incident, PriorityItem, WeekLog


# =============================================================================
# WeekLog Views
# =============================================================================


class WeekLogListView(LoginRequiredMixin, ListView):
    """List view for week logs with search and filtering."""

    model = WeekLog
    template_name = "logbook/weeklog_list.html"
    context_object_name = "weeklogs"
    paginate_by = 20

    def get_queryset(self):
        """Filter by year if specified."""
        queryset = super().get_queryset()
        year = self.request.GET.get("year")
        if year:
            queryset = queryset.filter(year=year)
        return queryset

    def get_context_data(self, **kwargs) -> dict:
        """Add available years for filtering."""
        context = super().get_context_data(**kwargs)
        context["years"] = (
            WeekLog.objects.values_list("year", flat=True).distinct().order_by("-year")
        )
        context["selected_year"] = self.request.GET.get("year")
        return context

    def get_template_names(self) -> list[str]:
        """Return partial template for HTMX requests."""
        if self.request.htmx:
            return ["logbook/partials/weeklog_list_items.html"]
        return [self.template_name]


class WeekLogDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single week log."""

    model = WeekLog
    template_name = "logbook/weeklog_detail.html"
    context_object_name = "weeklog"

    def get_context_data(self, **kwargs) -> dict:
        """Add forms for inline item creation."""
        context = super().get_context_data(**kwargs)
        context["priority_form"] = PriorityItemForm()
        context["absence_form"] = AbsenceForm()
        context["incident_form"] = IncidentForm()
        return context


class WeekLogCreateView(LoginRequiredMixin, CreateView):
    """Create view for new week logs."""

    model = WeekLog
    form_class = WeekLogForm
    template_name = "logbook/weeklog_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Set created_by before saving."""
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f"Ugelog for {self.object.week_label} oprettet.")
        return response

    def get_success_url(self) -> str:
        """Redirect to detail view after creation."""
        return reverse_lazy("logbook:weeklog-detail", kwargs={"pk": self.object.pk})


class WeekLogUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for existing week logs."""

    model = WeekLog
    form_class = WeekLogForm
    template_name = "logbook/weeklog_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Show success message."""
        response = super().form_valid(form)
        messages.success(self.request, "Ugelog opdateret.")
        return response

    def get_success_url(self) -> str:
        """Redirect back to detail view."""
        return reverse_lazy("logbook:weeklog-detail", kwargs={"pk": self.object.pk})


# =============================================================================
# Priority Item HTMX Views
# =============================================================================


class PriorityItemCreateView(LoginRequiredMixin, CreateView):
    """HTMX view for creating priority items inline."""

    model = PriorityItem
    form_class = PriorityItemForm
    template_name = "logbook/partials/priority_item_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Set weeklog from query param and return row partial plus OOB to close form."""
        weeklog_id = self.request.GET.get("weeklog")
        form.instance.weeklog_id = weeklog_id
        self.object = form.save()

        from django.template.loader import render_to_string

        # Render the new row
        row_html = render_to_string(
            "logbook/partials/priority_item_row.html",
            {"item": self.object},
            request=self.request,
        )
        # Add OOB swap to delete the form
        oob_html = '<div id="priority-item-form-container" hx-swap-oob="delete"></div>'

        return HttpResponse(row_html + oob_html)

    def form_invalid(self, form) -> HttpResponse:
        """Return form with errors."""
        response = super().form_invalid(form)
        response["HX-Retarget"] = "#priority-item-form-container"
        return response

    def get_context_data(self, **kwargs) -> dict:
        """Add weeklog ID to context."""
        context = super().get_context_data(**kwargs)
        context["weeklog_id"] = self.request.GET.get("weeklog")
        return context


class PriorityItemUpdateView(LoginRequiredMixin, UpdateView):
    """HTMX view for updating priority items inline."""

    model = PriorityItem
    form_class = PriorityItemForm
    template_name = "logbook/partials/priority_item_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Save and return updated row."""
        self.object = form.save()

        from django.template.response import TemplateResponse

        return TemplateResponse(
            self.request,
            "logbook/partials/priority_item_row.html",
            {"item": self.object},
        )


class PriorityItemDeleteView(LoginRequiredMixin, DeleteView):
    """HTMX view for deleting priority items."""

    model = PriorityItem

    def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Delete and return empty response for HTMX."""
        self.object = self.get_object()
        self.object.delete()
        return HttpResponse("")


# =============================================================================
# Absence HTMX Views
# =============================================================================


class AbsenceCreateView(LoginRequiredMixin, CreateView):
    """HTMX view for creating absences inline."""

    model = Absence
    form_class = AbsenceForm
    template_name = "logbook/partials/absence_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Set weeklog and return row partial plus OOB to close form."""
        weeklog_id = self.request.GET.get("weeklog")
        form.instance.weeklog_id = weeklog_id
        self.object = form.save()

        from django.template.loader import render_to_string

        # Render the new row
        row_html = render_to_string(
            "logbook/partials/absence_row.html",
            {"absence": self.object},
            request=self.request,
        )
        # Add OOB swap to delete the form
        oob_html = '<div id="absence-form-container" hx-swap-oob="delete"></div>'

        return HttpResponse(row_html + oob_html)

    def get_context_data(self, **kwargs) -> dict:
        """Add weeklog ID to context."""
        context = super().get_context_data(**kwargs)
        context["weeklog_id"] = self.request.GET.get("weeklog")
        return context


class AbsenceUpdateView(LoginRequiredMixin, UpdateView):
    """HTMX view for updating absences inline."""

    model = Absence
    form_class = AbsenceForm
    template_name = "logbook/partials/absence_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Save and return updated row."""
        self.object = form.save()

        from django.template.response import TemplateResponse

        return TemplateResponse(
            self.request,
            "logbook/partials/absence_row.html",
            {"absence": self.object},
        )


class AbsenceDeleteView(LoginRequiredMixin, DeleteView):
    """HTMX view for deleting absences."""

    model = Absence

    def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Delete and return empty response."""
        self.object = self.get_object()
        self.object.delete()
        return HttpResponse("")


# =============================================================================
# Incident HTMX Views
# =============================================================================


class IncidentCreateView(LoginRequiredMixin, CreateView):
    """HTMX view for creating incidents inline."""

    model = Incident
    form_class = IncidentForm
    template_name = "logbook/partials/incident_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Set weeklog and return row partial plus OOB to close form."""
        weeklog_id = self.request.GET.get("weeklog")
        form.instance.weeklog_id = weeklog_id
        self.object = form.save()

        from django.template.loader import render_to_string

        # Render the new row
        row_html = render_to_string(
            "logbook/partials/incident_row.html",
            {"incident": self.object},
            request=self.request,
        )
        # Add OOB swap to delete the form
        oob_html = '<div id="incident-form-container" hx-swap-oob="delete"></div>'

        return HttpResponse(row_html + oob_html)

    def get_context_data(self, **kwargs) -> dict:
        """Add weeklog ID to context."""
        context = super().get_context_data(**kwargs)
        context["weeklog_id"] = self.request.GET.get("weeklog")
        return context


class IncidentUpdateView(LoginRequiredMixin, UpdateView):
    """HTMX view for updating incidents inline."""

    model = Incident
    form_class = IncidentForm
    template_name = "logbook/partials/incident_form.html"

    def form_valid(self, form) -> HttpResponse:
        """Save and return updated row."""
        self.object = form.save()

        from django.template.response import TemplateResponse

        return TemplateResponse(
            self.request,
            "logbook/partials/incident_row.html",
            {"incident": self.object},
        )


class IncidentDeleteView(LoginRequiredMixin, DeleteView):
    """HTMX view for deleting incidents."""

    model = Incident

    def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Delete and return empty response."""
        self.object = self.get_object()
        self.object.delete()
        return HttpResponse("")


# =============================================================================
# Row Partial Views (for cancel operations)
# =============================================================================


@login_required
def priority_item_row(request: HttpRequest, pk: int) -> HttpResponse:
    """Return just the priority item row partial (for cancel)."""
    from django.template.response import TemplateResponse

    item = get_object_or_404(PriorityItem, pk=pk)
    return TemplateResponse(
        request, "logbook/partials/priority_item_row.html", {"item": item}
    )


@login_required
def absence_row(request: HttpRequest, pk: int) -> HttpResponse:
    """Return just the absence row partial (for cancel)."""
    from django.template.response import TemplateResponse

    absence = get_object_or_404(Absence, pk=pk)
    return TemplateResponse(
        request, "logbook/partials/absence_row.html", {"absence": absence}
    )


@login_required
def incident_row(request: HttpRequest, pk: int) -> HttpResponse:
    """Return just the incident row partial (for cancel)."""
    from django.template.response import TemplateResponse

    incident = get_object_or_404(Incident, pk=pk)
    return TemplateResponse(
        request, "logbook/partials/incident_row.html", {"incident": incident}
    )


# =============================================================================
# Export Views
# =============================================================================


@login_required
def export_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    """Export a week log as PDF."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    pdf_content = generate_pdf(weeklog)

    filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.pdf"
    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_markdown(request: HttpRequest, pk: int) -> HttpResponse:
    """Export a week log as Markdown."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    md_content = generate_markdown(weeklog)

    filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.md"
    response = HttpResponse(md_content, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_html(request: HttpRequest, pk: int) -> HttpResponse:
    """Export a week log as HTML."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    html_content = generate_html(weeklog)

    filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.html"
    response = HttpResponse(html_content, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_email(request: HttpRequest, pk: int) -> HttpResponse:
    """Send a week log via email."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    success, message = send_weeklog_email(weeklog)

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect("logbook:weeklog-detail", pk=pk)
