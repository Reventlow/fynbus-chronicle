"""Feature-request views — board, create, edit, status transitions."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models as db_models
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.permissions import EditorRequiredMixin, editor_required

from .forms import FeatureRequestEditForm, FeatureRequestForm
from .models import FeatureRequest


@login_required
def nav_badge(request: HttpRequest) -> HttpResponse:
    """Tiny partial — just the notification pill (or empty span if zero).

    Polled by the global nav every 60s so the badge updates when feature
    requests are submitted, marked in-progress, or solved without forcing
    a full page reload. Returns the same `<span>` shape as nav.html so an
    `outerHTML` swap leaves the polling loop intact.
    """
    count = FeatureRequest.objects.filter(
        Q(status=FeatureRequest.Status.OPEN)
        | Q(status=FeatureRequest.Status.IN_PROGRESS)
    ).count()
    return render(request, "feedback/_nav_badge.html", {"OPEN_FEEDBACK_COUNT": count})


@login_required
def board(request: HttpRequest) -> HttpResponse:
    """Three-column kanban: open / in_progress / solved."""
    qs = FeatureRequest.objects.select_related("submitted_by", "solved_by")

    # Optional filters: ?category=ui&q=foo
    q = (request.GET.get("q") or "").strip()
    category = request.GET.get("category") or ""
    importance = request.GET.get("importance") or ""

    if q:
        qs = qs.filter(
            db_models.Q(title__icontains=q)
            | db_models.Q(description__icontains=q)
            | db_models.Q(resolution_notes__icontains=q)
        )
    if category:
        qs = qs.filter(category=category)
    if importance:
        qs = qs.filter(importance=importance)

    open_items = qs.filter(status=FeatureRequest.Status.OPEN).order_by("order", "-created_at")
    in_progress_items = qs.filter(status=FeatureRequest.Status.IN_PROGRESS).order_by(
        "order", "-created_at"
    )
    solved_items = qs.filter(status=FeatureRequest.Status.SOLVED).order_by("-solved_at")[:50]

    return render(
        request,
        "feedback/board.html",
        {
            "open_items": open_items,
            "in_progress_items": in_progress_items,
            "solved_items": solved_items,
            "q": q,
            "category": category,
            "importance": importance,
            "categories": FeatureRequest.Category.choices,
            "importances": FeatureRequest.Importance.choices,
            "total_open": open_items.count(),
            "total_in_progress": in_progress_items.count(),
            "total_solved": FeatureRequest.objects.filter(
                status=FeatureRequest.Status.SOLVED
            ).count(),
        },
    )


class FeatureRequestCreateView(LoginRequiredMixin, CreateView):
    """Anyone authenticated can submit a feature request."""

    model = FeatureRequest
    form_class = FeatureRequestForm
    template_name = "feedback/form.html"

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user
        # Append at the end of the open column.
        max_order = FeatureRequest.objects.filter(
            status=FeatureRequest.Status.OPEN
        ).aggregate(m=db_models.Max("order"))["m"]
        form.instance.order = (max_order or 0) + 1
        response = super().form_valid(form)
        messages.success(self.request, "Tak — forslaget er sendt og lagt i Åbne.")
        return response

    def get_success_url(self):
        return reverse_lazy("feedback:board")


class FeatureRequestDetailView(LoginRequiredMixin, DetailView):
    model = FeatureRequest
    template_name = "feedback/detail.html"
    context_object_name = "request_obj"


class FeatureRequestUpdateView(EditorRequiredMixin, UpdateView):
    """Editors can edit any field (title, description, category, importance,
    status, resolution_notes)."""

    model = FeatureRequest
    form_class = FeatureRequestEditForm
    template_name = "feedback/form.html"

    def form_valid(self, form):
        # If the editor is flipping to solved via this form, stamp solved_by/at.
        was_solved_before = (
            FeatureRequest.objects.filter(pk=form.instance.pk)
            .values_list("status", flat=True)
            .first()
            == FeatureRequest.Status.SOLVED
        )
        response = super().form_valid(form)
        if (
            self.object.status == FeatureRequest.Status.SOLVED
            and not was_solved_before
        ):
            self.object.solved_by = self.request.user
            from django.utils import timezone

            self.object.solved_at = timezone.now()
            self.object.save(update_fields=["solved_by", "solved_at"])
            self.object.notify_submitter_solved(actor=self.request.user)
        elif (
            self.object.status != FeatureRequest.Status.SOLVED
            and was_solved_before
        ):
            self.object.solved_by = None
            self.object.solved_at = None
            self.object.save(update_fields=["solved_by", "solved_at"])
        messages.success(self.request, "Forslag opdateret.")
        return response

    def get_success_url(self):
        return reverse_lazy("feedback:detail", kwargs={"pk": self.object.pk})


@login_required
@editor_required
@require_POST
def mark_solved(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(FeatureRequest, pk=pk)
    obj.mark_solved(by=request.user)
    messages.success(request, f"”{obj.title}” markeret som løst.")
    return redirect(request.META.get("HTTP_REFERER") or reverse_lazy("feedback:board"))


@login_required
@editor_required
@require_POST
def reopen(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(FeatureRequest, pk=pk)
    obj.reopen()
    messages.success(request, f"”{obj.title}” genåbnet.")
    return redirect(request.META.get("HTTP_REFERER") or reverse_lazy("feedback:board"))


@login_required
@editor_required
@require_POST
def reorder(request: HttpRequest) -> JsonResponse:
    """Drag-reorder + cross-column status change.

    Body: ``{"open": [id, id, ...], "in_progress": [...], "solved": [...]}``
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    valid_statuses = {s.value for s in FeatureRequest.Status}
    for status, ids in data.items():
        if status not in valid_statuses or not isinstance(ids, list):
            continue
        for position, item_id in enumerate(ids):
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                continue
            obj = FeatureRequest.objects.filter(pk=item_id).first()
            if obj is None:
                continue
            updates = {"order": position}
            if obj.status != status:
                updates["status"] = status
                # Stamp solved_at if dragging into solved
                if status == FeatureRequest.Status.SOLVED and obj.solved_at is None:
                    from django.utils import timezone

                    updates["solved_at"] = timezone.now()
                    updates["solved_by"] = request.user
                elif status != FeatureRequest.Status.SOLVED:
                    updates["solved_at"] = None
                    updates["solved_by"] = None
            FeatureRequest.objects.filter(pk=item_id).update(**updates)
            if "solved_by" in updates and updates["solved_by"] is not None:
                obj.notify_submitter_solved(actor=request.user)
    return JsonResponse({"ok": True})
