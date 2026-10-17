"""
Helpers behind the v3 Kontrolpanel: the headline sentence, sync freshness,
the "Åbne sager" bento and the changelog strip.

Kept free of request handling so the views stay thin and the wording
rules can be tested on their own.
"""

import math
import re
from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import timezone

from apps.logbook.models import HelpdeskTicket, WeekLog

# Danish words for small counts, as the headline spells them out ("fire færre").
_NUMBER_WORDS = {1: "én", 2: "to", 3: "tre", 4: "fire", 5: "fem", 6: "seks",
                 7: "syv", 8: "otte", 9: "ni", 10: "ti"}


def count_words(n: int) -> str:
    """1–10 spelled out in Danish, numerals above (and for 0)."""
    return _NUMBER_WORDS.get(n, str(n))


def headline_delta(delta: int | None) -> dict | None:
    """The "fire færre / tre flere / uændret" part of the headline.

    ``delta`` is this week's net change in open tickets (new − closed),
    i.e. open now versus the end of last week. Returns ``{text, tone}``
    with tone ``good``, ``bad`` or ``flat``, or None when unknown.
    """
    if delta is None:
        return None
    if delta < 0:
        return {"text": f"{count_words(-delta)} færre", "tone": "good"}
    if delta > 0:
        return {"text": f"{count_words(delta)} flere", "tone": "bad"}
    return {"text": "uændret", "tone": "flat"}


_MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def sync_state(now: datetime | None = None) -> dict:
    """When the ServiceDesk mirror last synced, and whether that is stale.

    The scheduler syncs every ``SERVICEDESK_SYNC_INTERVAL`` seconds and
    each run re-saves at least the newest ticket, so the newest
    ``synced_at`` is the time of the last successful run. Three missed
    runs (at least 15 minutes) count as a failing sync.
    """
    now = now or timezone.now()
    last = (
        HelpdeskTicket.objects.order_by("-synced_at").values_list("synced_at", flat=True).first()
    )
    interval = getattr(settings, "SERVICEDESK_SYNC_INTERVAL", 300)
    limit = timedelta(seconds=max(3 * interval, 15 * 60))
    # "kl 08:40" today, "15. okt kl 08:40" for an older sync (headline, meta line).
    label = ""
    if last is not None:
        local = timezone.localtime(last)
        label = f"kl {local:%H:%M}"
        if local.date() != timezone.localtime(now).date():
            label = f"{local.day}. {_MONTHS[local.month - 1]} {label}"
    return {"last_sync": last, "label": label, "stale": last is None or now - last > limit}


# The bento's four age groups, built from the week log's seven buckets:
# (label, bucket fields, colour token).
AGE_GROUPS = (
    ("< 1 uge", ("helpdesk_open_0_7",), "var(--good)"),
    ("1–4 uger", ("helpdesk_open_8_14", "helpdesk_open_15_30"), "var(--accent)"),
    ("1–3 mdr", ("helpdesk_open_31_90",), "var(--warn)"),
    ("> 3 mdr", ("helpdesk_open_91_180", "helpdesk_open_181_365", "helpdesk_open_over_365"), "var(--bad)"),
)


def age_groups(weeklog: WeekLog | None) -> dict | None:
    """Open tickets in four age groups for the bento, or None without data.

    Returns ``{groups: [{label, count, share, color}], total, over_3_months}``.
    """
    if weeklog is None or not weeklog.has_helpdesk_age_breakdown:
        return None
    total = weeklog.helpdesk_open_bucketed
    groups = []
    for label, fields, color in AGE_GROUPS:
        count = sum(getattr(weeklog, f) or 0 for f in fields)
        groups.append({
            "label": label,
            "count": count,
            "share": round(100 * count / total, 1) if total else 0,
            "color": color,
        })
    return {"groups": groups, "total": total, "over_3_months": groups[-1]["count"]}


# Donut geometry (SVG units): radius and the gap between slices.
DONUT_R = 48
DONUT_GAP = 2


def donut_segments(slices: list[dict]) -> list[dict]:
    """Stroke-dasharray segments for an SVG donut of ``[{count, color, …}]``.

    Each segment keeps the input keys and adds ``dash`` / ``offset``
    strings for a circle of radius ``DONUT_R`` starting at 12 o'clock.
    """
    circumference = 2 * math.pi * DONUT_R
    total = sum(s["count"] for s in slices)
    if not total:
        return []
    out, offset = [], 0.0
    for s in slices:
        length = s["count"] / total * circumference
        visible = max(length - DONUT_GAP, 0.5) if len(slices) > 1 else length
        out.append({
            **s,
            "dash": f"{visible:.2f} {circumference - visible:.2f}",
            "offset": f"{-offset:.2f}",
        })
        offset += length
    return out


_TITLE_RE = re.compile(r"^(?P<version>\d+\.\d+\.\d+)\s*[—-]\s*(?P<date>\d{4}-\d{2}-\d{2})")
_FIRST_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def changelog_strip(title: str, body: str, today: date | None = None) -> dict:
    """Version, one-line summary and relative date for the changelog strip.

    ``title`` is a CHANGELOG heading ("0.20.12 — 2026-10-16"); the summary
    is the entry's first bold phrase, which is how entries open.
    """
    today = today or timezone.localdate()
    match = _TITLE_RE.match(title.strip())
    version = match["version"] if match else title.strip()
    when = ""
    if match:
        days = (today - date.fromisoformat(match["date"])).days
        when = {0: "i dag", 1: "i går"}.get(days, f"for {days} dage siden" if days > 1 else "")
    bold = _FIRST_BOLD_RE.search(body)
    # Drop the entry's inline *emphasis* markers; the strip is plain text.
    summary = bold.group(1).replace("*", "").rstrip(".") + "." if bold else ""
    return {"version": version, "summary": summary, "when": when}
