"""
Statistics for the "Statistik" page: one year of helpdesk and Chronicle data.

Helpdesk figures come from the ``HelpdeskTicket`` mirror (kept in step with
ServiceDesk by the scheduler); Chronicle figures come from priority tasks
(``PriorityItem``) and incidents (``Incident``). Everything is computed in
Python from a single query per model — a year is roughly a thousand
tickets, so this stays well under a tenth of a second.

Conventions used throughout:

* The window is the last 365 days, ending now.
* "Løst" (solved) means closed and not cancelled. Cancelled tickets still
  close a ticket for the open count, but are not credited as solved.
* Times are local (Europe/Copenhagen); a ticket written at 07:55 counts
  in the 07 hour.
* Resolution time is calendar time from creation to close, nights and
  weekends included — ServiceDesk does not expose business hours here.
"""

from collections import Counter
from datetime import date, datetime, timedelta
from statistics import mean, median

from django.utils import timezone

from apps.logbook.models import HelpdeskTicket, Incident, PriorityItem, WeekLog

WINDOW_DAYS = 365
WEEKS = 52

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


def _week_ends(now: datetime) -> list[tuple[date, datetime]]:
    """The last ``WEEKS`` ISO weeks as (monday, end instant), oldest first.

    The end of the current week is "now", so its open count is today's.
    """
    local_now = timezone.localtime(now)
    this_monday = local_now.date() - timedelta(days=local_now.weekday())
    weeks = []
    for i in range(WEEKS - 1, -1, -1):
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


def _month_keys(now: datetime) -> list[tuple[int, int]]:
    """The 12 calendar months ending with the current one, oldest first."""
    local = timezone.localtime(now)
    year, month = local.year, local.month
    keys = []
    for _ in range(12):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _month_label(key: tuple[int, int]) -> str:
    return f"{MONTHS_SHORT[key[1] - 1]} {str(key[0])[2:]}"


def helpdesk_statistics(now: datetime | None = None) -> dict:
    """Every helpdesk figure on the statistics page."""
    now = now or timezone.now()
    since = now - timedelta(days=WINDOW_DAYS)

    tickets = list(
        HelpdeskTicket.objects.only(
            "created_at", "closed_at", "is_open", "is_cancelled",
            "requester_ref", "category", "technician",
        )
    )
    created = [t for t in tickets if t.created_at >= since]
    solved = [
        t for t in tickets
        if t.closed_at is not None and t.closed_at >= since and not t.is_cancelled
    ]

    # --- Headline numbers ------------------------------------------------
    requesters = {t.requester_ref for t in created if t.requester_ref}

    # --- When people write: weekday × hour, as an average per such day ----
    # Divide by how many of each weekday the window holds, so a Monday
    # figure is "tickets on an average Monday", not a yearly total.
    day_counts = Counter()
    for offset in range(WINDOW_DAYS):
        day_counts[(timezone.localtime(now) - timedelta(days=offset)).weekday()] += 1

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
    heatmap = [
        {
            "day": WEEKDAYS_SHORT[d],
            "cells": [
                round(by_day_hour[(d, h)] / day_counts[d], 2) if day_counts[d] else 0
                for h in range(24)
            ],
        }
        for d in range(7)
    ]
    heat_max = max((c for row in heatmap for c in row["cells"]), default=0)
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
    weeks = _week_ends(now)
    weekly = []
    for monday, end in weeks:
        start = timezone.make_aware(datetime.combine(monday, datetime.min.time()))
        weekly.append({
            "label": _week_label(monday),
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

    # --- Solved per technician ---------------------------------------------
    technicians = Counter(_technician_label(t.technician) for t in solved)

    # --- Open now, by age ---------------------------------------------------
    now_ms = int(now.timestamp() * 1000)
    age_buckets = Counter()
    open_now = [t for t in tickets if t.is_open]
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
        "per_month": round(len(created) / 12, 1),
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
        "technicians": _shares(technicians),
        "open_by_age": open_by_age,
    }


def chronicle_statistics(now: datetime | None = None) -> dict:
    """Priority tasks and incidents ("nedbrud") over the same year."""
    now = now or timezone.now()
    since = now - timedelta(days=WINDOW_DAYS)
    months = _month_keys(now)

    def month_of(dt: datetime) -> tuple[int, int]:
        local = timezone.localtime(dt)
        return (local.year, local.month)

    # --- Priority tasks (soft-deleted and merged ones left out) -----------
    items = list(PriorityItem.objects.filter(deleted_at=None))
    created = [i for i in items if i.created_at >= since]
    completed = [
        i for i in items
        if i.status == PriorityItem.Status.COMPLETED and i.closed_at and i.closed_at >= since
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
    incidents = list(Incident.objects.filter(occurred_at__gte=since))
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
        "per_month": round(len(incidents) / 12, 1),
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
