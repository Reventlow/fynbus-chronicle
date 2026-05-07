"""Plain Python → JSON-friendly dicts for the Chronicle API.

No DRF — these are tiny helpers that turn ORM objects into the shape
external clients (MCP server, scripts) expect. Keeps the dependency tree
tight and the contract obvious.
"""

from typing import Any

from apps.logbook.models import Absence, Incident, PriorityItem, WeekLog
from apps.oncall.models import OnCallDuty


def serialize_priority_item(item: PriorityItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "priority": item.priority,
        "priority_display": item.get_priority_display(),
        "status": item.status,
        "status_display": item.get_status_display(),
        "notes": item.notes,
        "order": item.order,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def serialize_absence(absence: Absence) -> dict[str, Any]:
    return {
        "id": absence.id,
        "staff_name": absence.staff_name,
        "absence_type": absence.absence_type,
        "absence_type_display": absence.get_absence_type_display(),
        "start_date": absence.start_date.isoformat() if absence.start_date else None,
        "end_date": absence.end_date.isoformat() if absence.end_date else None,
        "notes": absence.notes,
    }


def serialize_incident(incident: Incident, *, include_weeklog: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": incident.id,
        "title": incident.title,
        "description": incident.description,
        "incident_type": incident.incident_type,
        "incident_type_display": incident.get_incident_type_display(),
        "severity": incident.severity,
        "severity_display": incident.get_severity_display(),
        "occurred_at": incident.occurred_at.isoformat() if incident.occurred_at else None,
        "resolved": incident.resolved,
        "resolution": incident.resolution,
    }
    if include_weeklog and incident.weeklog_id:
        data["weeklog"] = {"year": incident.weeklog.year, "week": incident.weeklog.week_number}
    return data


def serialize_weeklog(weeklog: WeekLog, *, full: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "year": weeklog.year,
        "week": weeklog.week_number,
        "label": weeklog.week_label,
        "helpdesk_new": weeklog.helpdesk_new,
        "helpdesk_closed": weeklog.helpdesk_closed,
        "helpdesk_open": weeklog.helpdesk_open,
        "helpdesk_delta": weeklog.helpdesk_delta,
        "summary": weeklog.summary,
        "created_by": weeklog.created_by.username if weeklog.created_by_id else None,
        "created_at": weeklog.created_at.isoformat() if weeklog.created_at else None,
        "updated_at": weeklog.updated_at.isoformat() if weeklog.updated_at else None,
    }
    if full:
        data["priority_items"] = [serialize_priority_item(p) for p in weeklog.priority_items.all()]
        data["absences"] = [serialize_absence(a) for a in weeklog.absences.all()]
        data["incidents"] = [serialize_incident(i, include_weeklog=False) for i in weeklog.incidents.all()]
        data["meeting_skipped"] = weeklog.meeting_skipped
        data["meeting_skipped_reason"] = weeklog.meeting_skipped_reason
        data["meeting_attendees"] = weeklog.meeting_attendees
        data["meeting_minutes"] = weeklog.meeting_minutes
    return data


def serialize_oncall(duty: OnCallDuty | None) -> dict[str, Any] | None:
    if duty is None:
        return None
    return {
        "year": duty.year,
        "week": duty.week_number,
        "label": duty.week_label,
        "user": {
            "username": duty.user.username,
            "full_name": duty.user.get_full_name() or duty.user.username,
            "email": duty.user.email,
        },
        "notes": duty.notes,
    }
