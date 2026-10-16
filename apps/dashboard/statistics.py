"""
Statistics for the "Statistik" page: one year of helpdesk and Chronicle data.

Helpdesk figures come from the ``HelpdeskTicket`` mirror (kept in step with
ServiceDesk by the scheduler); Chronicle figures come from priority tasks
(``PriorityItem``) and incidents (``Incident``). Everything is computed in
Python from a single query per model — a year is roughly a thousand
tickets, so this stays well under a tenth of a second.

Conventions used throughout:

* The window defaults to the last 365 days, ending now. The page can ask
  for another period (``Period``); every window-shaped figure follows it.
  "Open" figures are a snapshot at the end of the period: live from the
  ServiceDesk status when the period ends now, otherwise rebuilt from the
  open and close times.
* "Løst" (solved) means closed and not cancelled. Cancelled tickets still
  close a ticket for the open count, but are not credited as solved.
* Times are local (Europe/Copenhagen); a ticket written at 07:55 counts
  in the 07 hour.
* Resolution time is calendar time from creation to close, nights and
  weekends included — ServiceDesk does not expose business hours here.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import mean, median
from urllib.parse import urlencode

from django.utils import timezone

from apps.logbook.models import HelpdeskTicket, Incident, PriorityItem, WeekLog

WINDOW_DAYS = 365
WEEKS = 52
DAYS_PER_MONTH = 365 / 12

WEEKDAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]
WEEKDAYS_SHORT = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
MONTHS_SHORT = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

# Resolution-time buckets: (label, upper bound in hours or None).
RESOLUTION_BUCKETS = (
    ("Under 1 time", 1),
    ("1–4 timer", 4),
    ("4–24 timer", 24),
    ("1–3 dage", 72),
    ("3–7 dage", 168),
    ("1–4 uger", 672),
    ("Over 4 uger", None),
)

NO_CATEGORY = "Ingen kategori"
NO_DEPARTMENT = "Ingen afdeling"
UNASSIGNED = "Ikke tildelt"
ANONYMISED = "Anonymiseret tekniker"


def _technician_label(name: str) -> str:
    """Display name for a technician; ServiceDesk anonymises leavers as ANONYMOUS_<id>."""
    if not name:
        return UNASSIGNED
    if name.startswith("ANONYMOUS_"):
        return ANONYMISED
    return name


def _shares(counter: Counter, total: int | None = None) -> list[dict]:
    """``[{label, count, share}]`` sorted by count, share in percent."""
    total = total if total is not None else sum(counter.values())
    return [
        {"label": label, "count": count, "share": round(100 * count / total, 1) if total else 0}
        for label, count in counter.most_common()
    ]


def _hours(delta: timedelta) -> float:
    return delta.total_seconds() / 3600


def _format_duration(hours: float | None) -> str:
    """Human Danish duration: '45 min', '5,2 t', '3,4 dage'."""
    if hours is None:
        return "—"
    if hours < 1:
        return f"{round(hours * 60)} min"
    if hours < 48:
        return f"{hours:.1f} t".replace(".", ",")
    return f"{hours / 24:.1f} dage".replace(".", ",")


@dataclass(frozen=True)
class Period:
    """The window the statistics cover: ``start`` (inclusive) to ``end``.

    ``live`` means the period ends at the present moment, so "open" figures
    can use the live ServiceDesk status instead of being rebuilt.
    """

    start: datetime
    end: datetime
    is_default: bool = True
    live: bool = True

    @property
    def days(self) -> float:
        return (self.end - self.start).total_seconds() / 86400

    @property
    def months(self) -> float:
        """Length in average months; exactly 12 for the default 365 days."""
        return self.days / DAYS_PER_MONTH

    @property
    def week_count(self) -> int:
        """ISO weeks in the weekly series: 52 by default, else every week touched."""
        if self.is_default:
            return WEEKS
        first = self.first_day - timedelta(days=self.first_day.weekday())
        last = self.last_day - timedelta(days=self.last_day.weekday())
        return (last - first).days // 7 + 1

    @property
    def month_count(self) -> int:
        """Calendar months in the monthly series: 12 by default, else every month touched."""
        if self.is_default:
            return 12
        first, last = self.first_day, self.last_day
        return (last.year - first.year) * 12 + last.month - first.month + 1

    @property
    def first_day(self) -> date:
        return timezone.localtime(self.start).date()

    @property
    def last_day(self) -> date:
        """The last calendar day inside the period (``end`` is exclusive)."""
        return timezone.localtime(self.end - timedelta(microseconds=1)).date()

    @property
    def label(self) -> str:
        return "Seneste 12 måneder" if self.is_default else "Valgt periode"

    @property
    def open_label(self) -> str:
        return "Åbne lige nu" if self.live else "Åbne ved periodens slutning"

    @property
    def query(self) -> str:
        """``fra=…&til=…`` for links that must keep the period; empty by default."""
        if self.is_default:
            return ""
        return urlencode({"fra": self.first_day.isoformat(), "til": self.last_day.isoformat()})


def default_period(now: datetime | None = None) -> Period:
    """The last 365 days, ending now."""
    now = now or timezone.now()
    return Period(start=now - timedelta(days=WINDOW_DAYS), end=now)


def _parse_day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _local_midnight(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min))


def period_from_params(params, now: datetime | None = None) -> tuple[Period, str | None]:
    """The period asked for in ``?fra=YYYY-MM-DD&til=YYYY-MM-DD``.

    Both days are inclusive. A missing ``til`` (or one today or later)
    ends the period now; a missing ``fra`` starts it 365 days before the
    end. Returns the period and an error message (Danish) when the input
    could not be used, in which case the period is the default one.
    """
    now = now or timezone.now()
    raw_from, raw_to = params.get("fra") or "", params.get("til") or ""
    if not raw_from and not raw_to:
        return default_period(now), None
    first, last = _parse_day(raw_from), _parse_day(raw_to)
    if (raw_from and first is None) or (raw_to and last is None):
        return default_period(now), "Ugyldig dato. Viser de seneste 12 måneder."

    end = now
    if last is not None:
        end = min(_local_midnight(last + timedelta(days=1)), now)
    start = _local_midnight(first) if first is not None else end - timedelta(days=WINDOW_DAYS)
    if start >= end:
        return default_period(now), "Startdatoen skal ligge før slutdatoen. Viser de seneste 12 måneder."
    return Period(start=start, end=end, is_default=False, live=end >= now), None


def _week_ends(now: datetime, count: int = WEEKS) -> list[tuple[date, datetime]]:
    """The last ``count`` ISO weeks up to ``now``, as (monday, end instant), oldest first.

    The last week ends at ``now``, so its open count is the one at the end
    of the period.
    """
    # ``now`` may be a period end at midnight; that instant belongs to the day before.
    last_day = timezone.localtime(now - timedelta(microseconds=1)).date()
    this_monday = last_day - timedelta(days=last_day.weekday())
    weeks = []
    for i in range(count - 1, -1, -1):
        monday = this_monday - timedelta(weeks=i)
        if i == 0:
            end = now
        else:
            next_monday = datetime.combine(monday + timedelta(days=7), datetime.min.time())
            end = timezone.make_aware(next_monday)
        weeks.append((monday, end))
    return weeks


def _week_label(monday: date) -> str:
    return f"U{monday.isocalendar()[1]}"


def _month_keys(now: datetime, count: int = 12) -> list[tuple[int, int]]:
    """The ``count`` calendar months ending with the one ``now`` is in, oldest first."""
    local = timezone.localtime(now - timedelta(microseconds=1))
    year, month = local.year, local.month
    keys = []
    for _ in range(count):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _month_label(key: tuple[int, int]) -> str:
    return f"{MONTHS_SHORT[key[1] - 1]} {str(key[0])[2:]}"


def helpdesk_statistics(now: datetime | None = None, period: Period | None = None) -> dict:
    """Every helpdesk figure on the statistics page, for ``period``
    (default: the 365 days ending at ``now``)."""
    period = period or default_period(now)
    since, until = period.start, period.end

    tickets = list(
        HelpdeskTicket.objects.only(
            "created_at", "closed_at", "is_open", "is_cancelled",
            "requester_ref", "department", "category", "technician",
        )
    )
    created = [t for t in tickets if since <= t.created_at < until]
    solved = [
        t for t in tickets
        if t.closed_at is not None and since <= t.closed_at < until and not t.is_cancelled
    ]

    # --- Headline numbers ------------------------------------------------
    requesters = {t.requester_ref for t in created if t.requester_ref}

    # --- When people write: weekday × hour, as an average per such day ----
    # Divide by how many of each weekday the window holds, so a Monday
    # figure is "tickets on an average Monday", not a yearly total.
    day_counts = Counter()
    day = period.first_day
    while day <= period.last_day:
        day_counts[day.weekday()] += 1
        day += timedelta(days=1)

    by_day = Counter()
    by_day_hour = Counter()
    by_hour = Counter()
    for t in created:
        local = timezone.localtime(t.created_at)
        by_day[local.weekday()] += 1
        by_day_hour[(local.weekday(), local.hour)] += 1
        by_hour[local.hour] += 1

    weekday_avg = [
        round(by_day[d] / day_counts[d], 2) if day_counts[d] else 0 for d in range(7)
    ]
    # Each cell carries the year's count (printed in the cell, and what the
    # colour scales with) and the average per such weekday (tooltip).
    heatmap = [
        {
            "day": WEEKDAYS_SHORT[d],
            "cells": [
                {
                    "hour": h,
                    "count": by_day_hour[(d, h)],
                    "avg": round(by_day_hour[(d, h)] / day_counts[d], 2) if day_counts[d] else 0,
                }
                for h in range(24)
            ],
        }
        for d in range(7)
    ]
    heat_max = max((c["count"] for row in heatmap for c in row["cells"]), default=0)
    busiest_day = max(range(7), key=lambda d: weekday_avg[d]) if created else None
    busiest_hour = max(range(24), key=lambda h: by_hour[h]) if created else None

    # --- How fast: created in the window and solved -----------------------
    durations = sorted(
        _hours(t.closed_at - t.created_at)
        for t in created
        if t.closed_at is not None and not t.is_cancelled and t.closed_at >= t.created_at
    )
    resolution_buckets = Counter()
    for hours in durations:
        for label, upper in RESOLUTION_BUCKETS:
            if upper is None or hours < upper:
                resolution_buckets[label] += 1
                break
    n_dur = len(durations)
    resolution = {
        "count": n_dur,
        "median": _format_duration(median(durations)) if durations else "—",
        "mean": _format_duration(mean(durations)) if durations else "—",
        "p90": _format_duration(durations[min(n_dur - 1, int(0.9 * n_dur))]) if durations else "—",
        "within_day": round(100 * sum(1 for h in durations if h < 24) / n_dur) if n_dur else 0,
        # The same figures as plain numbers (hours), for the JSON export.
        "median_hours": round(median(durations), 2) if durations else None,
        "mean_hours": round(mean(durations), 2) if durations else None,
        "p90_hours": round(durations[min(n_dur - 1, int(0.9 * n_dur))], 2) if durations else None,
        "buckets": [
            {
                "label": label,
                "count": resolution_buckets[label],
                "share": round(100 * resolution_buckets[label] / n_dur, 1) if n_dur else 0,
            }
            for label, _ in RESOLUTION_BUCKETS
        ],
    }

    # --- Per week: created, solved, open at week end ----------------------
    weeks = _week_ends(until, period.week_count)
    weekly = []
    for monday, end in weeks:
        start = timezone.make_aware(datetime.combine(monday, datetime.min.time()))
        weekly.append({
            "label": _week_label(monday),
            "week_start": monday,
            "created": sum(1 for t in tickets if start <= t.created_at < end),
            "solved": sum(
                1 for t in tickets
                if t.closed_at and not t.is_cancelled and start <= t.closed_at < end
            ),
            # Open at the end of the week: created by then, not yet closed.
            "open": sum(
                1 for t in tickets
                if t.created_at < end and (t.closed_at is None or t.closed_at >= end)
            ),
        })

    # --- Categories (created in the window) --------------------------------
    categories = Counter(t.category or NO_CATEGORY for t in created)
    uncategorised = categories.get(NO_CATEGORY, 0)
    categorised = Counter({k: v for k, v in categories.items() if k != NO_CATEGORY})

    # --- Departments (created in the window) -------------------------------
    # The requester's department as ServiceDesk holds it on the last sync.
    departments = Counter(t.department or NO_DEPARTMENT for t in created)

    # --- Solved per technician ---------------------------------------------
    technicians = Counter(_technician_label(t.technician) for t in solved)

    # --- Open at the end of the period, by age -------------------------------
    now_ms = int(until.timestamp() * 1000)
    age_buckets = Counter()
    if period.live:
        open_now = [t for t in tickets if t.is_open]
    else:
        open_now = [
            t for t in tickets
            if t.created_at < until and (t.closed_at is None or t.closed_at >= until)
        ]
    for t in open_now:
        age_days = max(0, (now_ms - int(t.created_at.timestamp() * 1000)) // 86_400_000)
        for field, label, _low, high, color in WeekLog.HELPDESK_AGE_BUCKETS:
            if high is None or age_days <= high:
                age_buckets[field] += 1
                break
    open_by_age = [
        {
            "label": label,
            "count": age_buckets[field],
            "color": color,
            "share": round(100 * age_buckets[field] / len(open_now), 1) if open_now else 0,
        }
        for field, label, _low, _high, color in WeekLog.HELPDESK_AGE_BUCKETS
    ]

    last_sync = (
        HelpdeskTicket.objects.order_by("-synced_at").values_list("synced_at", flat=True).first()
    )

    return {
        "has_data": bool(tickets),
        "last_sync": last_sync,
        "total_created": len(created),
        "total_solved": len(solved),
        "cancelled": sum(1 for t in created if t.is_cancelled),
        "requesters": len(requesters),
        "per_month": round(len(created) / period.months, 1),
        "per_requester": round(len(created) / len(requesters), 1) if requesters else 0,
        "open_now": len(open_now),
        "weekday_avg": [
            {"day": WEEKDAYS[d], "short": WEEKDAYS_SHORT[d], "avg": weekday_avg[d]} for d in range(7)
        ],
        "heatmap": heatmap,
        "heat_max": heat_max,
        "busiest_day": WEEKDAYS[busiest_day] if busiest_day is not None else None,
        "busiest_hour": busiest_hour,
        "resolution": resolution,
        "weekly": weekly,
        "categories": _shares(categorised),
        "uncategorised": uncategorised,
        "uncategorised_share": round(100 * uncategorised / len(created)) if created else 0,
        "departments": _shares(departments),
        # Rows per column when the list is split in two (ranked top-down).
        "department_rows": (len(departments) + 1) // 2,
        "technicians": _shares(technicians),
        "open_by_age": open_by_age,
    }


def chronicle_statistics(now: datetime | None = None, period: Period | None = None) -> dict:
    """Priority tasks and incidents ("nedbrud") over the same period.

    "Active" tasks and their status are always today's: task status
    history is not stored, so it cannot be rebuilt for a past date.
    """
    period = period or default_period(now)
    since, until = period.start, period.end
    months = _month_keys(until, period.month_count)

    def month_of(dt: datetime) -> tuple[int, int]:
        local = timezone.localtime(dt)
        return (local.year, local.month)

    # --- Priority tasks (soft-deleted and merged ones left out) -----------
    items = list(PriorityItem.objects.filter(deleted_at=None))
    created = [i for i in items if since <= i.created_at < until]
    completed = [
        i for i in items
        if i.status == PriorityItem.Status.COMPLETED and i.closed_at and since <= i.closed_at < until
    ]
    active = [i for i in items if i.status != PriorityItem.Status.COMPLETED]
    lead_days = [
        (i.closed_at - i.created_at).total_seconds() / 86400
        for i in completed
        if i.closed_at >= i.created_at
    ]
    created_by_month = Counter(month_of(i.created_at) for i in created)
    completed_by_month = Counter(month_of(i.closed_at) for i in completed)
    status_labels = dict(PriorityItem.Status.choices)
    priority_labels = dict(PriorityItem.Priority.choices)

    priorities = {
        "created": len(created),
        "completed": len(completed),
        "auto_closed": sum(1 for i in completed if i.auto_closed),
        "active": len(active),
        "median_days": round(median(lead_days)) if lead_days else None,
        "by_status": [
            {"label": status_labels[s], "count": sum(1 for i in active if i.status == s)}
            for s in (
                PriorityItem.Status.NOT_STARTED,
                PriorityItem.Status.ONGOING,
                PriorityItem.Status.BLOCKED,
            )
        ],
        "by_priority": _shares(Counter(priority_labels[i.priority] for i in created)),
        "months": [_month_label(m) for m in months],
        "created_by_month": [created_by_month[m] for m in months],
        "completed_by_month": [completed_by_month[m] for m in months],
    }

    # --- Incidents ("nedbrud") --------------------------------------------
    incidents = list(Incident.objects.filter(occurred_at__gte=since, occurred_at__lt=until))
    type_labels = dict(Incident.IncidentType.choices)
    severity_labels = dict(Incident.Severity.choices)
    by_month = Counter(month_of(i.occurred_at) for i in incidents)
    severity_order = [
        Incident.Severity.CRITICAL,
        Incident.Severity.HIGH,
        Incident.Severity.MEDIUM,
        Incident.Severity.LOW,
    ]

    incident_stats = {
        "total": len(incidents),
        "resolved": sum(1 for i in incidents if i.resolved),
        "unresolved": sum(1 for i in incidents if not i.resolved),
        "critical": sum(1 for i in incidents if i.severity == Incident.Severity.CRITICAL),
        "per_month": round(len(incidents) / period.months, 1),
        "by_type": _shares(Counter(type_labels[i.incident_type] for i in incidents)),
        "by_severity": [
            {
                "label": severity_labels[s],
                "key": str(s),
                "count": sum(1 for i in incidents if i.severity == s),
            }
            for s in severity_order
        ],
        "months": [_month_label(m) for m in months],
        "by_month": [by_month[m] for m in months],
    }

    return {"priorities": priorities, "incidents": incident_stats}
