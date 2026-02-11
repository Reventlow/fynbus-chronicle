"""
Views for the on-call duty application.

Provides a calendar grid for self-service week assignment
and HTMX endpoints for claiming/releasing weeks.
"""

from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.generic import TemplateView

from .models import OnCallDuty


def _get_week_dates(year: int, week: int) -> tuple[datetime, datetime]:
    """Get Monday and Sunday dates for a given ISO year/week."""
    monday = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u").date()
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _build_weeks_context(user) -> list[dict]:
    """Build context data for 13 weeks starting from current week."""
    now = timezone.now()
    iso = now.isocalendar()
    current_year, current_week = iso.year, iso.week

    weeks = []
    # Start from current week, iterate 13 weeks
    date = now.date() - timedelta(days=now.weekday())  # Monday of current week
    for i in range(13):
        week_date = date + timedelta(weeks=i)
        iso_cal = week_date.isocalendar()
        year, week = iso_cal[0], iso_cal[1]
        monday, sunday = _get_week_dates(year, week)

        duty = OnCallDuty.get_for_week(year, week)

        weeks.append({
            "year": year,
            "week": week,
            "monday": monday,
            "sunday": sunday,
            "duty": duty,
            "is_current": year == current_year and week == current_week,
            "is_own": duty and duty.user == user,
        })

    return weeks


def _render_week_card(request, year: int, week: int) -> str:
    """Render a single week card partial."""
    now = timezone.now()
    iso = now.isocalendar()
    monday, sunday = _get_week_dates(year, week)
    duty = OnCallDuty.get_for_week(year, week)

    context = {
        "week": {
            "year": year,
            "week": week,
            "monday": monday,
            "sunday": sunday,
            "duty": duty,
            "is_current": year == iso.year and week == iso.week,
            "is_own": duty and duty.user == request.user,
        },
        "request": request,
    }
    return render_to_string("oncall/partials/week_card.html", context, request=request)


class OnCallCalendarView(LoginRequiredMixin, TemplateView):
    """Calendar grid showing 13 weeks of on-call assignments."""

    template_name = "oncall/calendar.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["weeks"] = _build_weeks_context(self.request.user)
        return context


@login_required
def oncall_claim(request, year: int, week: int) -> HttpResponse:
    """HTMX endpoint to claim an on-call week."""
    if request.method != "POST":
        return HttpResponse(status=405)

    # Only create if not already claimed
    _, created = OnCallDuty.objects.get_or_create(
        year=year,
        week_number=week,
        defaults={"user": request.user},
    )

    return HttpResponse(_render_week_card(request, year, week))


@login_required
def oncall_release(request, year: int, week: int) -> HttpResponse:
    """HTMX endpoint to release an on-call week (only your own)."""
    if request.method != "POST":
        return HttpResponse(status=405)

    OnCallDuty.objects.filter(
        year=year,
        week_number=week,
        user=request.user,
    ).delete()

    return HttpResponse(_render_week_card(request, year, week))
