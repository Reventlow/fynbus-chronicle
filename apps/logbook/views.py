"""
Views for the logbook application.

Provides views for WeekLog CRUD operations and HTMX partials
for inline editing of priority items, absences, and incidents.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models as db_models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.accounts.permissions import EditorRequiredMixin, editor_required

from .exports.email import send_weeklog_email
from .exports.html import generate_html
from .exports.markdown import generate_markdown
from .exports.pdf import generate_pdf
from .forms import AbsenceForm, IncidentForm, MeetingMinutesForm, PriorityItemForm, WeekLogForm
from .models import Absence, Incident, PriorityItem, PriorityItemAppearance, WeekLog


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

    def get_object(self, queryset=None):
        weeklog = super().get_object(queryset)
        # If we're looking at the current ISO-week weeklog, run the
        # auto-close pass so anything older than 6 weeks is tidied up
        # before we render. Carry-over is intentionally NOT automatic —
        # users pick open tasks via the "Tilføj eksisterende" dialog.
        current = WeekLog.get_current_week()
        if current is not None and current.pk == weeklog.pk:
            weeklog.auto_close_stale_priorities()
        return weeklog

    def get_context_data(self, **kwargs) -> dict:
        """Add forms for inline item creation + appearances queryset."""
        context = super().get_context_data(**kwargs)
        context["priority_form"] = PriorityItemForm()
        context["absence_form"] = AbsenceForm()
        context["incident_form"] = IncidentForm()
        context["priority_appearances"] = (
            self.object.priority_appearances.select_related("priority_item")
            .order_by("order", "id")
        )
        return context


class WeekLogCreateView(EditorRequiredMixin, CreateView):
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


class WeekLogUpdateView(EditorRequiredMixin, UpdateView):
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


class PriorityItemCreateView(EditorRequiredMixin, CreateView):
    """HTMX view: create a new priority task on a given weeklog.

    Creates both the long-lived ``PriorityItem`` and its first
    ``PriorityItemAppearance`` for the weeklog the form was opened on.
    """

    model = PriorityItem
    form_class = PriorityItemForm
    template_name = "logbook/partials/priority_item_form.html"

    def form_valid(self, form) -> HttpResponse:
        weeklog_id = self.request.GET.get("weeklog")
        weeklog = get_object_or_404(WeekLog, pk=weeklog_id)
        form.instance.origin_weeklog = weeklog
        item = form.save()

        # Create the matching appearance for this weeklog with the
        # description carried in the form.
        max_order = (
            weeklog.priority_appearances.aggregate(m=db_models.Max("order"))["m"]
            or 0
        )
        appearance = PriorityItemAppearance.objects.create(
            priority_item=item,
            weeklog=weeklog,
            description=form.cleaned_data.get("description", "") or "",
            order=max_order + 1,
        )

        from django.template.loader import render_to_string

        row_html = render_to_string(
            "logbook/partials/priority_item_row.html",
            {"appearance": appearance, "item": item},
            request=self.request,
        )
        oob_html = '<div id="priority-item-form-container" hx-swap-oob="delete"></div>'
        return HttpResponse(row_html + oob_html)

    def form_invalid(self, form) -> HttpResponse:
        response = super().form_invalid(form)
        response["HX-Retarget"] = "#priority-item-form-container"
        return response

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["weeklog_id"] = self.request.GET.get("weeklog")
        return context


class PriorityItemUpdateView(EditorRequiredMixin, UpdateView):
    """HTMX view: edit a priority appearance row.

    The URL pk refers to ``PriorityItemAppearance`` — the row in the
    weeklog UI. Form-saved fields update the underlying long-lived
    ``PriorityItem``; the ``description`` field updates this week's
    appearance only. Toggling the status from completed → active
    triggers ``reopen()`` and auto-adds the task to the current week.
    """

    model = PriorityItem
    form_class = PriorityItemForm
    template_name = "logbook/partials/priority_item_form.html"

    def get_object(self, queryset=None):  # type: ignore[override]
        appearance = get_object_or_404(
            PriorityItemAppearance.objects.select_related("priority_item", "weeklog"),
            pk=self.kwargs["pk"],
        )
        self._appearance = appearance
        return appearance.priority_item

    def get_initial(self) -> dict:
        initial = super().get_initial()
        initial["description"] = self._appearance.description
        return initial

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["appearance"] = self._appearance
        return context

    def form_valid(self, form) -> HttpResponse:
        item = form.save(commit=False)
        # Was the item completed before this save?
        was_completed = (
            self.model.objects.filter(pk=item.pk)
            .values_list("status", flat=True)
            .first()
            == self.model.Status.COMPLETED
        )
        item.touch(save=False)
        item.save()

        # Update this week's appearance description.
        self._appearance.description = form.cleaned_data.get("description", "") or ""
        self._appearance.save(update_fields=["description", "updated_at"])

        # Reopen flow: completed → active auto-adds to the current ISO week.
        if was_completed and item.status != self.model.Status.COMPLETED:
            current = WeekLog.get_current_week()
            if current is not None:
                item.reopen(into_weeklog=current)

        from django.template.response import TemplateResponse

        return TemplateResponse(
            self.request,
            "logbook/partials/priority_item_row.html",
            {"appearance": self._appearance, "item": item},
        )


class PriorityItemDeleteView(EditorRequiredMixin, DeleteView):
    """HTMX view: remove a task from a single week (deletes the appearance).

    The long-lived PriorityItem stays intact and may still be visible
    on other weeks. Use the admin or the search page to delete a task
    entirely.
    """

    model = PriorityItemAppearance

    def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        self.object = self.get_object()
        self.object.delete()
        return HttpResponse("")


@login_required
@editor_required
@require_POST
def reorder_priority_items(request: HttpRequest) -> HttpResponse:
    """Reorder appearances within a week via drag-and-drop."""
    try:
        data = json.loads(request.body)
        order_ids = data.get("order", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    for position, appearance_id in enumerate(order_ids):
        PriorityItemAppearance.objects.filter(pk=appearance_id).update(order=position)
    return HttpResponse(status=204)


# ---------------------------------------------------------------------------
# Priority search + carry-from-open dialog + history
# ---------------------------------------------------------------------------


@login_required
def priorities_search(request: HttpRequest) -> HttpResponse:
    """Search across all priority tasks (open + closed).

    Filters: ``q`` (text in title/notes/appearance descriptions),
    ``status`` ('open' / 'closed' / 'all', default 'all'), ``year``.
    """
    qs = PriorityItem.objects.select_related("origin_weeklog").prefetch_related("appearances")
    q = (request.GET.get("q") or "").strip()
    status_filter = request.GET.get("status") or "all"
    year = request.GET.get("year")

    if q:
        qs = qs.filter(
            db_models.Q(title__icontains=q)
            | db_models.Q(notes__icontains=q)
            | db_models.Q(appearances__description__icontains=q)
        ).distinct()
    if status_filter == "open":
        qs = qs.exclude(status=PriorityItem.Status.COMPLETED)
    elif status_filter == "closed":
        qs = qs.filter(status=PriorityItem.Status.COMPLETED)
    if year and year.isdigit():
        qs = qs.filter(origin_weeklog__year=int(year))

    qs = qs.order_by("-last_active_at")[:100]
    years = (
        WeekLog.objects.values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )

    from django.shortcuts import render

    return render(
        request,
        "logbook/priorities_search.html",
        {
            "items": qs,
            "q": q,
            "status_filter": status_filter,
            "year": year,
            "years": years,
        },
    )


@login_required
def priority_item_history(request: HttpRequest, pk: int) -> HttpResponse:
    """All appearances of a single task across weeks (the history view)."""
    item = get_object_or_404(
        PriorityItem.objects.select_related("origin_weeklog"), pk=pk
    )
    appearances = (
        item.appearances.select_related("weeklog")
        .order_by("-weeklog__year", "-weeklog__week_number")
    )
    from django.shortcuts import render

    return render(
        request,
        "logbook/priority_item_history.html",
        {"item": item, "appearances": appearances},
    )


@login_required
@editor_required
def weeklog_add_existing_dialog(request: HttpRequest, pk: int) -> HttpResponse:
    """Render the 'pick open tasks to bring forward' dialog for a weeklog.

    GET → returns the dialog body (HTMX swap target). Lists priority
    items that are still active and don't already have an appearance
    on this weeklog. Optional ``?q=`` text filter.
    """
    weeklog = get_object_or_404(WeekLog, pk=pk)
    q = (request.GET.get("q") or "").strip()
    already = weeklog.priority_appearances.values_list("priority_item_id", flat=True)
    qs = (
        PriorityItem.objects.exclude(status=PriorityItem.Status.COMPLETED)
        .exclude(pk__in=already)
        .select_related("origin_weeklog")
        .order_by("-last_active_at")
    )
    if q:
        qs = qs.filter(
            db_models.Q(title__icontains=q) | db_models.Q(notes__icontains=q)
        )
    qs = qs[:50]
    from django.shortcuts import render

    return render(
        request,
        "logbook/partials/add_existing_dialog.html",
        {"weeklog": weeklog, "items": qs, "q": q},
    )


@login_required
@editor_required
def priority_item_merge_dialog(request: HttpRequest, pk: int) -> HttpResponse:
    """Render the merge dialog: pick another active task to fold ``pk`` into.

    GET only. Lists every active priority item except the loser itself,
    filterable by ``?q=`` text. The dialog POSTs to ``priority-item-merge-post``.
    """
    loser = get_object_or_404(PriorityItem, pk=pk)
    q = (request.GET.get("q") or "").strip()
    qs = (
        PriorityItem.objects.exclude(pk=loser.pk)
        .exclude(status=PriorityItem.Status.COMPLETED)
        .select_related("origin_weeklog")
        .order_by("-last_active_at")
    )
    if q:
        qs = qs.filter(
            db_models.Q(title__icontains=q) | db_models.Q(notes__icontains=q)
        )
    qs = qs[:50]

    from django.shortcuts import render

    return render(
        request,
        "logbook/partials/merge_dialog.html",
        {"loser": loser, "candidates": qs, "q": q},
    )


@login_required
@editor_required
@require_POST
def priority_item_merge_post(
    request: HttpRequest, loser_pk: int, winner_pk: int
) -> HttpResponse:
    """Execute the merge and redirect to the winner's most recent weeklog."""
    loser = get_object_or_404(PriorityItem, pk=loser_pk)
    winner = get_object_or_404(PriorityItem, pk=winner_pk)
    try:
        loser_title = loser.title  # snapshot before deletion
        loser.merge_into(winner)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("logbook:priority-item-history", pk=winner.pk)

    messages.success(
        request,
        f"”{loser_title}” flettet ind i ”{winner.title}”.",
    )
    # Send the user to the winner's most recent weeklog so they can see
    # the merged history land on familiar ground.
    target_appearance = winner.appearances.order_by(
        "-weeklog__year", "-weeklog__week_number"
    ).first()
    if target_appearance is not None:
        return redirect("logbook:weeklog-detail", pk=target_appearance.weeklog.pk)
    return redirect("logbook:priority-item-history", pk=winner.pk)


@login_required
@editor_required
@require_POST
def weeklog_add_existing_post(request: HttpRequest, pk: int) -> HttpResponse:
    """Carry the chosen open tasks into ``weeklog`` as new appearances."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    item_ids = request.POST.getlist("item_ids")
    try:
        ids = [int(i) for i in item_ids]
    except ValueError:
        ids = []
    added = weeklog.add_existing_priority_items(ids)
    if added:
        messages.success(
            request,
            f"{added} {'opgave' if added == 1 else 'opgaver'} tilføjet til {weeklog.week_label}.",
        )
    else:
        messages.info(request, "Ingen opgaver tilføjet.")
    return redirect("logbook:weeklog-detail", pk=weeklog.pk)


# =============================================================================
# Absence HTMX Views
# =============================================================================


class AbsenceCreateView(EditorRequiredMixin, CreateView):
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


class AbsenceUpdateView(EditorRequiredMixin, UpdateView):
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


class AbsenceDeleteView(EditorRequiredMixin, DeleteView):
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


class IncidentCreateView(EditorRequiredMixin, CreateView):
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


class IncidentUpdateView(EditorRequiredMixin, UpdateView):
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


class IncidentDeleteView(EditorRequiredMixin, DeleteView):
    """HTMX view for deleting incidents."""

    model = Incident

    def delete(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Delete and return empty response."""
        self.object = self.get_object()
        self.object.delete()
        return HttpResponse("")


# =============================================================================
# Meeting Minutes HTMX Views
# =============================================================================


@login_required
@editor_required
def meeting_minutes_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """HTMX view for editing meeting attendees and minutes inline."""
    from django.template.response import TemplateResponse

    weeklog = get_object_or_404(WeekLog, pk=pk)

    if request.method == "POST":
        form = MeetingMinutesForm(request.POST, instance=weeklog)
        if form.is_valid():
            form.save()
            return TemplateResponse(
                request,
                "logbook/partials/meeting_minutes_card.html",
                {"weeklog": weeklog},
            )
    else:
        form = MeetingMinutesForm(instance=weeklog)

    return TemplateResponse(
        request,
        "logbook/partials/meeting_minutes_form.html",
        {"form": form, "weeklog": weeklog},
    )


@login_required
def meeting_minutes_card(request: HttpRequest, pk: int) -> HttpResponse:
    """Return the meeting minutes display card (for cancel)."""
    from django.template.response import TemplateResponse

    weeklog = get_object_or_404(WeekLog, pk=pk)
    return TemplateResponse(
        request,
        "logbook/partials/meeting_minutes_card.html",
        {"weeklog": weeklog},
    )


# =============================================================================
# Row Partial Views (for cancel operations)
# =============================================================================


@login_required
def priority_item_row(request: HttpRequest, pk: int) -> HttpResponse:
    """Return just the priority appearance row partial (for cancel/refresh)."""
    from django.template.response import TemplateResponse

    appearance = get_object_or_404(
        PriorityItemAppearance.objects.select_related("priority_item", "weeklog"),
        pk=pk,
    )
    return TemplateResponse(
        request,
        "logbook/partials/priority_item_row.html",
        {"appearance": appearance, "item": appearance.priority_item},
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
@editor_required
def export_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    """Export a week log as PDF."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    pdf_content = generate_pdf(weeklog)

    filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.pdf"
    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@editor_required
def export_markdown(request: HttpRequest, pk: int) -> HttpResponse:
    """Export a week log as Markdown."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    md_content = generate_markdown(weeklog)

    filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.md"
    response = HttpResponse(md_content, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@editor_required
def export_html(request: HttpRequest, pk: int) -> HttpResponse:
    """Export a week log as HTML."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    html_content = generate_html(weeklog)

    filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.html"
    response = HttpResponse(html_content, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@editor_required
def export_email(request: HttpRequest, pk: int) -> HttpResponse:
    """Send a week log via email."""
    weeklog = get_object_or_404(WeekLog, pk=pk)
    format = request.GET.get("format", "both")
    success, message = send_weeklog_email(
        weeklog, format=format, from_email=request.user.email
    )

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect("logbook:weeklog-detail", pk=pk)
