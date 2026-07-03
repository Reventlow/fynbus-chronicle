"""
Views for the on-call duty application.

Provides a calendar grid (current + optional past weeks) with
self-service claim/release, an assign form for switching the person
mid-week (FR #5), and a per-week history panel (coverage + audit).

All mutations go through ``services`` — see the module docstring there.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.permissions import editor_required

from . import services
from .forms import OnCallAssignForm
from .models import OnCallChange, OnCallDuty, OnCallSegment, week_span


def _get_week_dates(year: int, week: int) -> tuple[date, date]:
    """Get Monday and Sunday dates for a given ISO year/week."""
    monday = date.fromisocalendar(year, week, 1)
    return monday, monday + timedelta(days=6)


def valid_week_required(view_func):
    """404 instead of 500 for URL year/week values outside the ISO calendar."""

    @wraps(view_func)
    def _wrapped(request, year: int, week: int, *args, **kwargs):
        try:
            date.fromisocalendar(year, week, 1)
        except ValueError:
            raise Http404(f"Uge {week}, {year} findes ikke") from None
        return view_func(request, year, week, *args, **kwargs)

    return _wrapped


def _week_dict(
    user,
    year: int,
    week: int,
    duty: OnCallDuty | None,
    segments: list[OnCallSegment],
    has_changes: bool,
    today: date,
) -> dict:
    """Context dict for one week card."""
    monday, sunday = _get_week_dates(year, week)
    iso = today.isocalendar()
    now = timezone.localtime()
    for segment in segments:
        segment.is_now = segment.start_at <= now < segment.end_at
    return {
        "year": year,
        "week": week,
        "monday": monday,
        "sunday": sunday,
        "duty": duty,
        "segments": segments,
        # A freed week can keep several past segments — it must still
        # render as "Ledig" with the claim button, not as split/staffed.
        "is_split": duty is not None and len(segments) > 1,
        "has_changes": has_changes,
        "is_current": year == iso.year and week == iso.week,
        "is_past": sunday < today,
        "is_own": bool(duty and duty.user == user),
    }


def _build_weeks_context(user, num_weeks: int = 13, past_weeks: int = 0) -> list[dict]:
    """Context for the calendar grid: optional past weeks + coming weeks.

    Batched: three queries for the whole span instead of one per card.
    """
    today = timezone.localdate()
    first_monday = today - timedelta(days=today.weekday()) - timedelta(weeks=past_weeks)

    week_keys = []
    for i in range(past_weeks + num_weeks):
        iso_cal = (first_monday + timedelta(weeks=i)).isocalendar()
        week_keys.append((iso_cal[0], iso_cal[1]))

    span_start = week_span(*week_keys[0])[0]
    span_end = week_span(*week_keys[-1])[1]

    duties = {
        (d.year, d.week_number): d
        for d in OnCallDuty.objects.filter(
            year__in={y for y, _ in week_keys}
        ).select_related("user")
    }
    segments_by_week: dict[tuple[int, int], list[OnCallSegment]] = defaultdict(list)
    for segment in (
        OnCallSegment.objects.filter(start_at__gte=span_start, start_at__lt=span_end)
        .select_related("user")
        .order_by("start_at")
    ):
        segments_by_week[(segment.year, segment.week_number)].append(segment)
    changed_weeks = set(
        OnCallChange.objects.filter(year__in={y for y, _ in week_keys})
        .values_list("year", "week_number")
        .distinct()
    )

    return [
        _week_dict(
            user,
            year,
            week,
            duties.get((year, week)),
            segments_by_week.get((year, week), []),
            (year, week) in changed_weeks,
            today,
        )
        for year, week in week_keys
    ]


def _render_week_card(request, year: int, week: int) -> str:
    """Render a single week card partial."""
    context = {
        "week": _week_dict(
            request.user,
            year,
            week,
            OnCallDuty.get_for_week(year, week),
            list(OnCallSegment.for_week(year, week)),
            OnCallChange.objects.filter(year=year, week_number=week).exists(),
            timezone.localdate(),
        ),
        "request": request,
    }
    return render_to_string("oncall/partials/week_card.html", context, request=request)


def _render_week_form(request, year: int, week: int, form: OnCallAssignForm) -> str:
    """Render the non-polling assign-form card partial."""
    context = {
        "week": _week_dict(
            request.user,
            year,
            week,
            OnCallDuty.get_for_week(year, week),
            list(OnCallSegment.for_week(year, week)),
            False,
            timezone.localdate(),
        ),
        "form": form,
    }
    return render_to_string("oncall/partials/week_card_form.html", context, request=request)


ALLOWED_WEEK_RANGES = {13, 56}
ALLOWED_PAST_RANGES = {0, 4, 13, 26}


class OnCallCalendarView(LoginRequiredMixin, TemplateView):
    """Calendar grid showing on-call assignments."""

    template_name = "oncall/calendar.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        try:
            num_weeks = int(self.request.GET.get("weeks", 13))
        except (TypeError, ValueError):
            num_weeks = 13
        if num_weeks not in ALLOWED_WEEK_RANGES:
            num_weeks = 13
        try:
            past_weeks = int(self.request.GET.get("past", 0))
        except (TypeError, ValueError):
            past_weeks = 0
        if past_weeks not in ALLOWED_PAST_RANGES:
            past_weeks = 0
        context["weeks"] = _build_weeks_context(self.request.user, num_weeks, past_weeks)
        context["num_weeks"] = num_weeks
        context["past_weeks"] = past_weeks
        return context


@login_required
@valid_week_required
def oncall_week_status(request, year: int, week: int) -> HttpResponse:
    """HTMX polling endpoint to refresh a single week card."""
    return HttpResponse(_render_week_card(request, year, week))


@login_required
@valid_week_required
@editor_required
def oncall_claim(request, year: int, week: int) -> HttpResponse:
    """HTMX endpoint to claim a free on-call week for yourself."""
    if request.method != "POST":
        return HttpResponse(status=405)

    services.claim_week(year, week, request.user)
    return HttpResponse(_render_week_card(request, year, week))


@login_required
@valid_week_required
@editor_required
def oncall_release(request, year: int, week: int) -> HttpResponse:
    """HTMX endpoint to release an on-call week (only your own)."""
    if request.method != "POST":
        return HttpResponse(status=405)

    services.release_week(year, week, request.user)
    return HttpResponse(_render_week_card(request, year, week))


@login_required
@valid_week_required
@editor_required
def oncall_assign_form(request, year: int, week: int) -> HttpResponse:
    """HTMX endpoint returning the assign form (swaps in place of the card)."""
    today = timezone.localdate()
    monday, sunday = _get_week_dates(year, week)
    default_date = today if monday <= today <= sunday else monday

    default_moment = timezone.make_aware(
        datetime.combine(default_date, time.min), timezone.get_default_timezone()
    )
    holder = OnCallSegment.covering(default_moment)
    duty = OnCallDuty.get_for_week(year, week)

    form = OnCallAssignForm(
        year,
        week,
        initial={
            "user": holder.user if holder else (duty.user if duty else None),
            "effective_date": default_date,
            "notes": duty.notes if duty else "",
        },
    )
    return HttpResponse(_render_week_form(request, year, week, form))


@login_required
@valid_week_required
@editor_required
def oncall_assign(request, year: int, week: int) -> HttpResponse:
    """HTMX endpoint applying an assignment change from the form."""
    if request.method != "POST":
        return HttpResponse(status=405)

    form = OnCallAssignForm(year, week, request.POST)
    if not form.is_valid():
        return HttpResponse(_render_week_form(request, year, week, form))

    services.apply_assignment(
        year,
        week,
        form.cleaned_data["user"],
        form.cleaned_data["effective_at"],
        changed_by=request.user,
        notes=form.cleaned_data["notes"],
    )
    return HttpResponse(_render_week_card(request, year, week))


@login_required
@valid_week_required
def oncall_history(request, year: int, week: int) -> HttpResponse:
    """HTMX endpoint for the per-week history panel (viewers may read)."""
    monday, sunday = _get_week_dates(year, week)
    context = {
        "year": year,
        "week": week,
        "monday": monday,
        "sunday": sunday,
        "segments": list(OnCallSegment.for_week(year, week)),
        "changes": OnCallChange.objects.filter(year=year, week_number=week).select_related(
            "from_user", "to_user", "changed_by"
        ),
    }
    return HttpResponse(
        render_to_string("oncall/partials/history_panel.html", context, request=request)
    )
