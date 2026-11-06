"""When the Planner sync runs: often in working hours, rarely outside.

``PLANNER_WORK_HOURS`` is e.g. ``"mon-fri 07:15-17:30"`` (Europe/Copenhagen,
the project's TIME_ZONE). Inside it the sync runs every
``PLANNER_INTERVAL_WORK`` seconds (default 120), otherwise every
``PLANNER_INTERVAL_OFF`` seconds (default 900). The end time is exclusive:
at 17:30 it is quiet hours.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass(frozen=True)
class WorkHours:
    days: frozenset[int]  # 0 = Monday
    start: time
    end: time

    def contains(self, moment: datetime) -> bool:
        local = timezone.localtime(moment)
        return local.weekday() in self.days and self.start <= local.time() < self.end


def parse_work_hours(spec: str) -> WorkHours:
    """Parse ``"mon-fri 07:15-17:30"`` (or ``"mon,wed 08:00-16:00"``)."""
    m = re.fullmatch(r"\s*([a-z,\-]+)\s+(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s*", spec.lower())
    if not m:
        raise ImproperlyConfigured(f"PLANNER_WORK_HOURS not understood: {spec!r}")
    days: set[int] = set()
    for part in m.group(1).split(","):
        if "-" in part:
            a, b = part.split("-")
            i, j = DAYS.index(a), DAYS.index(b)
            days.update(range(i, j + 1))
        else:
            days.add(DAYS.index(part))
    start = time(int(m.group(2)), int(m.group(3)))
    end = time(int(m.group(4)), int(m.group(5)))
    return WorkHours(frozenset(days), start, end)


def interval_for(moment: datetime | None = None) -> int:
    """Seconds until the next scheduled sync, counted from ``moment``."""
    moment = moment or timezone.now()
    hours = parse_work_hours(settings.PLANNER_WORK_HOURS)
    return settings.PLANNER_INTERVAL_WORK if hours.contains(moment) else settings.PLANNER_INTERVAL_OFF
