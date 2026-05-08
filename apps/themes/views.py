"""Manage themes + their date-based overruling schedules."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import editor_required

from .forms import ThemeScheduleForm
from .models import Theme, ThemeSchedule


@login_required
@editor_required
def manage(request: HttpRequest) -> HttpResponse:
    """Theme overview + per-theme schedule list with an add-form per theme.

    Themes themselves are still created in Django admin (each new theme
    needs CSS work in input.css), but date-based scheduling is the
    common task and lives here.
    """
    themes = (
        Theme.objects.filter(is_active=True)
        .prefetch_related("schedules")
        .order_by("name")
    )
    return render(
        request,
        "themes/manage.html",
        {"themes": themes, "form": ThemeScheduleForm()},
    )


@login_required
@editor_required
@require_POST
def schedule_create(request: HttpRequest, theme_pk: int) -> HttpResponse:
    theme = get_object_or_404(Theme, pk=theme_pk)
    form = ThemeScheduleForm(request.POST)
    if form.is_valid():
        sched = form.save(commit=False)
        sched.theme = theme
        sched.save()
        messages.success(
            request,
            f"Skedule tilføjet til ”{theme.name}” ({sched.start_date} – {sched.end_date}).",
        )
    else:
        # Surface the first error so the user knows what went wrong.
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Ugyldig skedule."
        messages.error(request, first_error)
    return redirect("themes:manage")


@login_required
@editor_required
@require_POST
def schedule_delete(request: HttpRequest, schedule_pk: int) -> HttpResponse:
    sched = get_object_or_404(ThemeSchedule, pk=schedule_pk)
    label = f"{sched.theme.name}: {sched.start_date} – {sched.end_date}"
    sched.delete()
    messages.success(request, f"Skedule slettet ({label}).")
    return redirect("themes:manage")
