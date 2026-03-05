"""
Views for the tasks application.

Provides class-based views for Task CRUD operations and
function-based HTMX partials for inline status changes,
notes, and chart data.
"""

import os

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.permissions import EditorRequiredMixin, editor_required

from .forms import TaskForm, TaskNoteForm, TaskStatusForm
from .models import Task, TaskNote, TaskNoteAttachment, TaskStateChange


# Valid sort fields and their ORM ordering expressions
SORT_OPTIONS = {
    "planned_start": "planned_start",
    "-planned_start": "-planned_start",
    "status": "status",
    "-status": "-status",
    "title": "title",
    "-title": "-title",
    "created_at": "created_at",
    "-created_at": "-created_at",
}

DEFAULT_SORT = ["planned_start", "created_at"]


def _get_sorted_task_queryset(request):
    """Return task queryset with sorting, select_related, and prefetch_related."""
    qs = Task.objects.select_related("created_by").prefetch_related(
        "assigned_to"
    )
    sort_param = request.GET.get("sort", "")
    if sort_param in SORT_OPTIONS:
        qs = qs.order_by(SORT_OPTIONS[sort_param])
    else:
        qs = qs.order_by(*DEFAULT_SORT)
    return qs


# =============================================================================
# Task Page Views (Class-Based)
# =============================================================================


class TaskListView(LoginRequiredMixin, ListView):
    """List view for all tasks with sortable columns."""

    model = Task
    template_name = "tasks/task_list.html"
    context_object_name = "tasks"

    def get_queryset(self):
        """Return tasks with sorting support."""
        return _get_sorted_task_queryset(self.request)

    def get_context_data(self, **kwargs):
        """Add current sort parameter to template context."""
        context = super().get_context_data(**kwargs)
        context["current_sort"] = self.request.GET.get("sort", "")
        return context


class TaskDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single task with notes and state history."""

    model = Task
    template_name = "tasks/task_detail.html"

    def get_queryset(self):
        """Prefetch related data for efficient rendering."""
        return Task.objects.select_related("created_by").prefetch_related(
            "notes",
            "notes__attachments",
            "notes__author",
            "state_changes",
            "state_changes__changed_by",
            "assigned_to",
        )

    def get_context_data(self, **kwargs):
        """Add status and note forms to context."""
        context = super().get_context_data(**kwargs)
        context["status_form"] = TaskStatusForm(instance=self.object)
        context["note_form"] = TaskNoteForm()
        return context


class TaskCreateView(EditorRequiredMixin, CreateView):
    """Create view for new tasks."""

    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    success_url = reverse_lazy("tasks:task-list")

    def form_valid(self, form):
        """Set created_by and record initial state change."""
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        TaskStateChange.objects.create(
            task=self.object,
            from_state="",
            to_state=self.object.status,
            changed_by=self.request.user,
        )
        return response


class TaskUpdateView(EditorRequiredMixin, UpdateView):
    """Update view for existing tasks."""

    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"

    def get_success_url(self):
        """Redirect to task detail page."""
        return reverse("tasks:task-detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        """Record state change if status was modified."""
        old_status = form.initial.get("status", "")
        new_status = form.cleaned_data.get("status", "")
        if old_status != new_status:
            TaskStateChange.objects.create(
                task=form.instance,
                from_state=old_status,
                to_state=new_status,
                changed_by=self.request.user,
            )
        return super().form_valid(form)


# =============================================================================
# HTMX Partial Views (Function-Based)
# =============================================================================


@login_required
@editor_required
def task_change_status(request, pk):
    """HTMX endpoint to change task status inline."""
    if request.method != "POST":
        return HttpResponse(status=405)

    task = get_object_or_404(Task, pk=pk)
    old_status = task.status

    form = TaskStatusForm(request.POST, instance=task)
    if form.is_valid():
        form.save()
        TaskStateChange.objects.create(
            task=task,
            from_state=old_status,
            to_state=task.status,
            changed_by=request.user,
        )
    return render(request, "tasks/partials/task_status_badge.html", {"task": task})


@login_required
@editor_required
def task_note_create(request, pk):
    """HTMX endpoint to create a note on a task."""
    if request.method != "POST":
        return HttpResponse(status=405)

    task = get_object_or_404(Task, pk=pk)
    form = TaskNoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.task = task
        note.author = request.user
        note.save()

        # Handle file attachments
        for f in request.FILES.getlist("files"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext in TaskNoteAttachment.ALLOWED_EXTENSIONS:
                TaskNoteAttachment.objects.create(
                    note=note,
                    file=f,
                    filename=f.name,
                )

        return render(
            request,
            "tasks/partials/task_note_row.html",
            {"note": note, "task": task},
        )

    # Return form with errors (422 for validation failure)
    return render(
        request,
        "tasks/partials/task_note_row.html",
        {"note": None, "task": task},
        status=422,
    )


@login_required
@editor_required
def task_note_delete(request, pk, note_pk):
    """HTMX endpoint to delete a note from a task."""
    if request.method != "DELETE":
        return HttpResponse(status=405)

    note = get_object_or_404(TaskNote, task__pk=pk, pk=note_pk)
    note.delete()
    return HttpResponse("")


@login_required
def task_row(request, pk):
    """HTMX endpoint to return a single task row partial."""
    if request.method != "GET":
        return HttpResponse(status=405)

    task = get_object_or_404(
        Task.objects.select_related("created_by").prefetch_related(
            "assigned_to"
        ),
        pk=pk,
    )
    return render(request, "tasks/partials/task_row.html", {"task": task})


@login_required
def task_list_partial(request):
    """HTMX endpoint to return the task list body partial."""
    if request.method != "GET":
        return HttpResponse(status=405)

    tasks = _get_sorted_task_queryset(request)
    return render(request, "tasks/partials/task_list_body.html", {"tasks": tasks})


@login_required
def task_chart_data(request):
    """API endpoint returning task data for Gantt chart rendering."""
    if request.method != "GET":
        return HttpResponse(status=405)

    tasks = (
        Task.objects.exclude(status=Task.Status.COMPLETE)
        .prefetch_related("state_changes", "assigned_to")
    )

    data = []
    for task in tasks:
        data.append({
            "id": task.pk,
            "title": task.title,
            "planned_start": task.planned_start.isoformat() if task.planned_start else None,
            "planned_end": task.planned_end.isoformat() if task.planned_end else None,
            "status": task.status,
            "state_changes": [
                {
                    "changed_at": sc.changed_at.isoformat(),
                    "from_state": sc.from_state,
                    "to_state": sc.to_state,
                }
                for sc in task.state_changes.all()
            ],
            "approvers": task.approvers,
            "assignees": [
                u.get_full_name() or u.username for u in task.assigned_to.all()
            ],
        })

    return JsonResponse(data, safe=False)
