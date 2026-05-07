"""Chronicle JSON API — read endpoints + write endpoints.

Read endpoints accept any active key (read or write scope).
Write endpoints require a write-scope key.

All responses are JSON. CSRF is disabled by the api_auth decorator.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.accounts.api_auth import api_auth
from apps.logbook.models import Absence, Incident, PriorityItem, WeekLog
from apps.oncall.models import OnCallDuty

from .serializers import (
    serialize_absence,
    serialize_incident,
    serialize_oncall,
    serialize_priority_item,
    serialize_weeklog,
)


def _parse_json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Body must be a JSON object")
    return data


# -------------------------------------------------------------------------
# Read endpoints (any scope)
# -------------------------------------------------------------------------


@require_GET
@api_auth(scope="read")
def weeklog_list(request: HttpRequest) -> JsonResponse:
    """List recent weeklogs (most recent first). ``?year=`` filters by year."""
    qs = WeekLog.objects.order_by("-year", "-week_number")
    year = request.GET.get("year")
    if year and year.isdigit():
        qs = qs.filter(year=int(year))
    qs = qs[:52]
    return JsonResponse({"weeklogs": [serialize_weeklog(w) for w in qs]})


@require_GET
@api_auth(scope="read")
def weeklog_current(request: HttpRequest) -> JsonResponse:
    """Current ISO-week weeklog with priority items, absences, incidents."""
    weeklog = WeekLog.get_current_week()
    if weeklog is None:
        return JsonResponse({"weeklog": None})
    return JsonResponse({"weeklog": serialize_weeklog(weeklog, full=True)})


@require_GET
@api_auth(scope="read")
def weeklog_detail(request: HttpRequest, year: int, week: int) -> JsonResponse:
    weeklog = get_object_or_404(WeekLog, year=year, week_number=week)
    return JsonResponse({"weeklog": serialize_weeklog(weeklog, full=True)})


@require_GET
@api_auth(scope="read")
def incidents_recent(request: HttpRequest) -> JsonResponse:
    """Recent incidents across all weeklogs."""
    limit = min(int(request.GET.get("limit", 20)), 100)
    qs = Incident.objects.select_related("weeklog").order_by("-occurred_at")[:limit]
    unresolved_count = Incident.objects.filter(resolved=False).count()
    return JsonResponse(
        {
            "incidents": [serialize_incident(i) for i in qs],
            "unresolved_count": unresolved_count,
        }
    )


@require_GET
@api_auth(scope="read")
def oncall_current(request: HttpRequest) -> JsonResponse:
    """Who's on call this ISO week."""
    duty = OnCallDuty.get_current()
    return JsonResponse({"oncall": serialize_oncall(duty)})


@require_GET
@api_auth(scope="read")
def helpdesk_data(request: HttpRequest) -> JsonResponse:
    """Last-52-week helpdesk numbers (same shape as the dashboard chart API)."""
    weeklogs = WeekLog.objects.order_by("-year", "-week_number")[:52]
    weeks_data = []
    for weeklog in reversed(list(weeklogs)):
        weeks_data.append(
            {
                "label": f"U{weeklog.week_number}",
                "year": weeklog.year,
                "week": weeklog.week_number,
                "new": weeklog.helpdesk_new,
                "closed": weeklog.helpdesk_closed,
                "open": weeklog.helpdesk_open,
            }
        )
    return JsonResponse({"weeks": weeks_data})


@require_GET
@api_auth(scope="read")
def changelog_latest(request: HttpRequest) -> JsonResponse:
    """First entry of CHANGELOG.md as plain markdown text."""
    changelog_file = Path(settings.BASE_DIR) / "CHANGELOG.md"
    if not changelog_file.exists():
        return JsonResponse({"latest": None})
    raw = changelog_file.read_text(encoding="utf-8")
    sections = re.split(r"^## ", raw, flags=re.MULTILINE)
    if len(sections) < 2:
        return JsonResponse({"latest": None})
    body = sections[1]
    title, _, rest = body.partition("\n")
    return JsonResponse({"latest": {"title": title.strip(), "body": rest.strip()}})


# -------------------------------------------------------------------------
# Write endpoints (write scope only)
# -------------------------------------------------------------------------


@require_POST
@api_auth(scope="write")
def priority_item_create(request: HttpRequest, year: int, week: int) -> JsonResponse:
    """Append a new priority item to the given weeklog."""
    weeklog = get_object_or_404(WeekLog, year=year, week_number=week)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    title = (data.get("title") or "").strip()
    if not title:
        return JsonResponse({"error": "missing_field", "detail": "title is required"}, status=400)
    item = PriorityItem.objects.create(
        weeklog=weeklog,
        title=title[:200],
        priority=data.get("priority", PriorityItem.Priority.MEDIUM),
        status=data.get("status", PriorityItem.Status.NOT_STARTED),
        notes=(data.get("notes") or "")[:2000],
    )
    return JsonResponse({"priority_item": serialize_priority_item(item)}, status=201)


@require_http_methods(["PATCH"])
@api_auth(scope="write")
def priority_item_update(request: HttpRequest, item_id: int) -> JsonResponse:
    item = get_object_or_404(PriorityItem, pk=item_id)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    for field in ("title", "priority", "status", "notes"):
        if field in data:
            value = data[field]
            if field in {"title", "notes"} and isinstance(value, str):
                value = value.strip()[: 200 if field == "title" else 2000]
            setattr(item, field, value)
    item.save()
    return JsonResponse({"priority_item": serialize_priority_item(item)})


@require_POST
@api_auth(scope="write")
def incident_create(request: HttpRequest, year: int, week: int) -> JsonResponse:
    weeklog = get_object_or_404(WeekLog, year=year, week_number=week)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    if not title or not description:
        return JsonResponse(
            {"error": "missing_field", "detail": "title and description are required"},
            status=400,
        )
    occurred_at_raw = data.get("occurred_at")
    if occurred_at_raw:
        try:
            occurred_at = datetime.fromisoformat(occurred_at_raw)
        except ValueError:
            return JsonResponse(
                {"error": "invalid_field", "detail": "occurred_at must be ISO-8601"},
                status=400,
            )
    else:
        occurred_at = timezone.now()
    incident = Incident.objects.create(
        weeklog=weeklog,
        title=title[:200],
        description=description,
        incident_type=data.get("incident_type", Incident.IncidentType.OTHER),
        severity=data.get("severity", Incident.Severity.MEDIUM),
        occurred_at=occurred_at,
        resolved=bool(data.get("resolved", False)),
        resolution=(data.get("resolution") or "").strip(),
    )
    return JsonResponse({"incident": serialize_incident(incident)}, status=201)
