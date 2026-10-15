"""
Keep the local HelpdeskTicket mirror in step with ServiceDesk Plus.

The statistics page needs individual tickets, not the weekly totals the
WeekLog keeps. This module copies the few fields it needs into
``HelpdeskTicket``:

``sync_full``
    Fetches every ticket created or closed within the last
    ``MIRROR_DAYS`` days, plus every ticket open now (however old), and
    removes mirror rows ServiceDesk no longer returns (deleted or merged
    tickets, or ones that have aged out of the window). Roughly 30 API
    calls for a year of tickets; the scheduler runs it once a day.

``sync_incremental``
    Fetches only tickets changed since the newest change already
    mirrored. One or two API calls; the scheduler runs it every cycle.
    Falls back to a full sync while the mirror is empty.

The open-ticket and age definitions are the same as the WeekLog sync
(``ServiceDeskClient.OPEN_STATUSES``), so the statistics page and the
dashboard count the same tickets.
"""

import logging
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from ..models import HelpdeskTicket
from .servicedesk import ServiceDeskClient

logger = logging.getLogger(__name__)

# The statistics cover one year; a few extra weeks let the "open per
# week" history reconstruct the first week of the window correctly.
MIRROR_DAYS = 400

# Re-read a margin before the newest mirrored change, so an edit saved in
# the same instant as the previous sync is never missed.
INCREMENTAL_OVERLAP = timedelta(hours=1)

# A year is about 1,100 tickets per listing; 50 pages leaves ample room.
MAX_PAGES = 50

TICKET_FIELDS = [
    "created_time",
    "completed_time",
    "resolved_time",
    "last_updated_time",
    "status",
    "requester",
    "category",
    "technician",
]

CANCELLED_STATUSES = {"Annulleret"}


def _ms_to_datetime(raw) -> datetime | None:
    """ServiceDesk ``{"value": "<epoch ms>"}`` (or a bare value) to an aware datetime."""
    value = raw.get("value") if isinstance(raw, dict) else raw
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=dt_timezone.utc)
    except (TypeError, ValueError):
        return None


def _name(raw) -> str:
    """The ``name`` of a ServiceDesk lookup object, or ''."""
    if not isinstance(raw, dict):
        return ""
    return raw.get("name") or ""


def ticket_values(row: dict) -> dict | None:
    """Turn one ServiceDesk request row into HelpdeskTicket field values.

    Returns None for a row without an id or creation time.
    """
    try:
        sdp_id = int(row.get("id"))
    except (TypeError, ValueError):
        return None
    created_at = _ms_to_datetime(row.get("created_time"))
    if created_at is None:
        return None

    status = _name(row.get("status"))
    is_open = status in ServiceDeskClient.OPEN_STATUSES
    updated_at = _ms_to_datetime(row.get("last_updated_time"))
    closed_at = None
    if not is_open:
        # Completed is the authoritative close time; a ticket that was only
        # resolved, or closed without either stamp, falls back gracefully.
        closed_at = (
            _ms_to_datetime(row.get("completed_time"))
            or _ms_to_datetime(row.get("resolved_time"))
            or updated_at
            or created_at
        )

    requester = row.get("requester") or {}
    return {
        "sdp_id": sdp_id,
        "created_at": created_at,
        "closed_at": closed_at,
        "status": status[:60],
        "is_open": is_open,
        "is_cancelled": status in CANCELLED_STATUSES,
        "requester_ref": str(requester.get("id") or "")[:40],
        "department": _name(requester.get("department"))[:120],
        "category": _name(row.get("category"))[:120],
        "technician": _name(row.get("technician"))[:120],
        "sdp_updated_at": updated_at,
    }


def _upsert(rows: list[dict]) -> set[int]:
    """Create or update a mirror row per request; returns the ids seen."""
    seen: set[int] = set()
    for row in rows:
        values = ticket_values(row)
        if values is None:
            continue
        sdp_id = values.pop("sdp_id")
        if sdp_id in seen:
            continue  # the full sync's listings overlap
        seen.add(sdp_id)
        HelpdeskTicket.objects.update_or_create(sdp_id=sdp_id, defaults=values)
    return seen


def _fetch(client: ServiceDeskClient, criteria: list[dict]) -> list[dict] | None:
    """One paged listing; None if it failed or was cut short by the page cap."""
    rows = client._fetch_paged(criteria, TICKET_FIELDS, max_pages=MAX_PAGES)
    if rows is not None and len(rows) >= MAX_PAGES * client.PAGE_SIZE:
        logger.warning("Ticket mirror listing hit the page cap; treating it as incomplete")
        return None
    return rows


def sync_full(client: ServiceDeskClient | None = None) -> int | None:
    """Refresh the whole mirror. Returns the number of tickets, or None on failure."""
    client = client or ServiceDeskClient()
    if not client.enabled:
        return None

    now_ms = int(timezone.now().timestamp() * 1000)
    since_ms = now_ms - MIRROR_DAYS * 86_400_000
    window = {"condition": "between", "values": [str(since_ms), str(now_ms)]}

    listings = [
        [{"field": "created_time", **window}],
        [{"field": "completed_time", **window}],
        [client._open_status_criterion()],
    ]
    rows: list[dict] = []
    for criteria in listings:
        part = _fetch(client, criteria)
        if part is None:
            # Never prune on a partial picture: it would delete live tickets.
            logger.error("Ticket mirror full sync aborted: a listing failed")
            return None
        rows += part

    with transaction.atomic():
        seen = _upsert(rows)
        removed, _ = HelpdeskTicket.objects.exclude(sdp_id__in=seen).delete()

    logger.info("Ticket mirror: full sync, %d tickets, %d removed", len(seen), removed)
    return len(seen)


def sync_incremental(client: ServiceDeskClient | None = None) -> int | None:
    """Fetch tickets changed since the last sync. Returns how many, or None on failure."""
    client = client or ServiceDeskClient()
    if not client.enabled:
        return None

    newest = (
        HelpdeskTicket.objects.exclude(sdp_updated_at=None)
        .order_by("-sdp_updated_at")
        .values_list("sdp_updated_at", flat=True)
        .first()
    )
    if newest is None:
        return sync_full(client)

    since_ms = int((newest - INCREMENTAL_OVERLAP).timestamp() * 1000)
    rows = _fetch(
        client,
        [{"field": "last_updated_time", "condition": "greater than", "value": str(since_ms)}],
    )
    if rows is None:
        return None

    with transaction.atomic():
        seen = _upsert(rows)
    logger.debug("Ticket mirror: %d changed tickets", len(seen))
    return len(seen)
