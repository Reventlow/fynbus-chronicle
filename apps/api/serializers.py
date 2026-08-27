"""Plain Python → JSON-friendly dicts for the Chronicle API.

No DRF — these are tiny helpers that turn ORM objects into the shape
external clients (MCP server, scripts) expect. Keeps the dependency tree
tight and the contract obvious.
"""

from typing import Any

from apps.feedback.models import FeatureRequest
from apps.logbook.models import (
    Absence,
    Incident,
    PriorityItem,
    PriorityItemAppearance,
    WeekLog,
)
from apps.oncall.models import OnCallChange, OnCallDuty, OnCallSegment


def serialize_feature_request(obj: FeatureRequest) -> dict[str, Any]:
    return {
        "id": obj.id,
        "title": obj.title,
        "description": obj.description,
        "category": obj.category,
        "category_display": obj.get_category_display(),
        "importance": obj.importance,
        "importance_display": obj.get_importance_display(),
        "status": obj.status,
        "status_display": obj.get_status_display(),
        "order": obj.order,
        "triggers_version_bump": obj.triggers_version_bump,
        "resolution_notes": obj.resolution_notes,
        "submitted_by": obj.submitted_by.username if obj.submitted_by_id else None,
        "solved_by": obj.solved_by.username if obj.solved_by_id else None,
        "solved_at": obj.solved_at.isoformat() if obj.solved_at else None,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def serialize_priority_item(item: PriorityItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "priority": item.priority,
        "priority_display": item.get_priority_display(),
        "status": item.status,
        "status_display": item.get_status_display(),
        "notes": item.notes,
        "auto_closed": item.auto_closed,
        "closed_at": item.closed_at.isoformat() if item.closed_at else None,
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
        "merged_into_id": item.merged_into_id,
        "last_active_at": (
            item.last_active_at.isoformat() if item.last_active_at else None
        ),
        "origin_weeklog": (
            {"year": item.origin_weeklog.year, "week": item.origin_weeklog.week_number}
            if item.origin_weeklog_id
            else None
        ),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def serialize_priority_appearance(
    appearance: PriorityItemAppearance,
    *,
    include_item: bool = True,
) -> dict[str, Any]:
    """Serialize one (task, week) appearance row.

    Includes the per-week ``description`` and ``order``. By default the
    nested long-lived task is included so callers don't need a second
    request to know what the row represents.
    """
    data: dict[str, Any] = {
        "id": appearance.id,
        "weeklog": {
            "year": appearance.weeklog.year,
            "week": appearance.weeklog.week_number,
        },
        "description": appearance.description,
        "order": appearance.order,
        "created_at": appearance.created_at.isoformat() if appearance.created_at else None,
        "updated_at": appearance.updated_at.isoformat() if appearance.updated_at else None,
    }
    if include_item:
        data["priority_item"] = serialize_priority_item(appearance.priority_item)
    return data


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
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        "created_by": (incident.created_by.username if incident.created_by_id else None),
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
        # Additive since 0.10.0 (FR #8): open tickets split by age
        # ("liggetid"). All-zero buckets mean the week has no breakdown.
        "helpdesk_open_by_age": [
            {
                "key": bucket["key"],
                "label": bucket["label"],
                "count": bucket["count"],
                "share": bucket["share"],
            }
            for bucket in weeklog.helpdesk_age_buckets
        ],
        "helpdesk_open_stale": weeklog.helpdesk_open_stale,
        "summary": weeklog.summary,
        "created_by": weeklog.created_by.username if weeklog.created_by_id else None,
        "created_at": weeklog.created_at.isoformat() if weeklog.created_at else None,
        "updated_at": weeklog.updated_at.isoformat() if weeklog.updated_at else None,
    }
    if full:
        data["priority_items"] = [
            serialize_priority_appearance(a)
            for a in weeklog.priority_appearances.select_related("priority_item")
            .filter(priority_item__deleted_at__isnull=True)
            .order_by("order", "id")
        ]
        data["absences"] = [serialize_absence(a) for a in weeklog.absences.all()]
        data["incidents"] = [serialize_incident(i, include_weeklog=False) for i in weeklog.incidents.all()]
        data["meeting_skipped"] = weeklog.meeting_skipped
        data["meeting_skipped_reason"] = weeklog.meeting_skipped_reason
        data["meeting_attendees"] = weeklog.meeting_attendees
        data["meeting_minutes"] = weeklog.meeting_minutes
        # Additive since 0.9.0 (FR #7): who has marked "nothing more to
        # add this week".
        data["signoffs"] = [
            {
                "username": s.user.username,
                "full_name": s.user.get_full_name() or s.user.username,
                "created_at": s.created_at.isoformat(),
            }
            for s in weeklog.signoffs.select_related("user").order_by("created_at")
        ]
    return data


def _serialize_oncall_user(user) -> dict[str, Any]:
    return {
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        "email": user.email,
    }


def serialize_oncall(duty: OnCallDuty | None) -> dict[str, Any] | None:
    """On-call duty for one week.

    Existing keys are contract-pinned (the MCP server passes this
    through verbatim): ``user`` stays a single object — for the current
    week ``get_current()`` resolves it to whoever covers *right now*.
    ``segments``/``changes`` were added in 0.8.0 (FR #5) and cover
    mid-week handovers and the audit trail.
    """
    if duty is None:
        return None
    segments = OnCallSegment.for_week(duty.year, duty.week_number)
    changes = OnCallChange.objects.filter(
        year=duty.year, week_number=duty.week_number
    ).select_related("from_user", "to_user", "changed_by")[:10]
    return {
        "year": duty.year,
        "week": duty.week_number,
        "label": duty.week_label,
        "user": _serialize_oncall_user(duty.user),
        "notes": duty.notes,
        "segments": [
            {
                "start_at": s.start_at.isoformat(),
                "end_at": s.end_at.isoformat(),
                "weekdays": s.range_label,
                "user": _serialize_oncall_user(s.user),
            }
            for s in segments
        ],
        "changes": [
            {
                "changed_at": c.changed_at.isoformat(),
                "changed_by": c.changed_by.username if c.changed_by_id else None,
                "from_user": c.from_user.username if c.from_user_id else None,
                "to_user": c.to_user.username if c.to_user_id else None,
                "effective_at": c.effective_at.isoformat(),
            }
            for c in changes
        ],
        "created_at": duty.created_at.isoformat() if duty.created_at else None,
        "updated_at": duty.updated_at.isoformat() if duty.updated_at else None,
    }
