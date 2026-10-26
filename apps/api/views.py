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
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.api_auth import api_auth
from apps.cves.models import CVE, CVECase, CVEComment, normalise_cve_id
from apps.feedback.models import FeatureRequest
from apps.logbook.models import (
    Incident,
    PriorityItem,
    PriorityItemAppearance,
    WeekLog,
)
from apps.oncall.models import OnCallDuty
from apps.reports.models import Report

from .serializers import (
    serialize_case,
    serialize_cve,
    serialize_feature_request,
    serialize_incident,
    serialize_oncall,
    serialize_priority_appearance,
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
                # Additive since 0.10.0 (FR #8): open tickets by age.
                "open_by_age": {
                    bucket["key"]: bucket["count"]
                    for bucket in weeklog.helpdesk_age_buckets
                },
                "open_stale": weeklog.helpdesk_open_stale,
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


@require_http_methods(["PATCH"])
@api_auth(scope="write")
def weeklog_helpdesk_age(request: HttpRequest, year: int, week: int) -> JsonResponse:
    """Set the open-ticket age ("liggetid") breakdown on a past weeklog.

    The ServiceDesk sync only ever fills in the *current* week, so a week
    that closed before the breakdown existed can only be filled in by hand
    or by reconstructing it from ticket history (see the
    ``backfill_liggetid`` management command). This endpoint is that
    write path.

    Body: one key per bucket field (missing buckets count as 0), plus an
    optional ``helpdesk_open`` to correct the recorded total. The buckets
    must add up to the open-ticket total, exactly as the weeklog form
    requires — a breakdown that does not add up would misreport the week.
    """
    weeklog = get_object_or_404(WeekLog, year=year, week_number=week)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)

    bucket_fields = [field for field, *_ in WeekLog.HELPDESK_AGE_BUCKETS]
    unknown = set(data) - set(bucket_fields) - {"helpdesk_open"}
    if unknown:
        return JsonResponse(
            {"error": "unknown_field", "detail": f"unknown fields: {sorted(unknown)}"},
            status=400,
        )

    buckets = {}
    for field in bucket_fields:
        value = data.get(field, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return JsonResponse(
                {"error": "invalid_value", "detail": f"{field} must be a non-negative integer"},
                status=400,
            )
        buckets[field] = value

    open_total = data.get("helpdesk_open", weeklog.helpdesk_open)
    if not isinstance(open_total, int) or isinstance(open_total, bool) or open_total < 0:
        return JsonResponse(
            {"error": "invalid_value", "detail": "helpdesk_open must be a non-negative integer"},
            status=400,
        )

    bucket_total = sum(buckets.values())
    if bucket_total and bucket_total != open_total:
        return JsonResponse(
            {
                "error": "breakdown_mismatch",
                "detail": (
                    f"buckets sum to {bucket_total} but helpdesk_open is {open_total}; "
                    "pass helpdesk_open to correct the total"
                ),
            },
            status=400,
        )

    weeklog.helpdesk_open = open_total
    for field, count in buckets.items():
        setattr(weeklog, field, count)
    weeklog.save(update_fields=["helpdesk_open", *bucket_fields, "updated_at"])

    return JsonResponse({"weeklog": serialize_weeklog(weeklog)})


@require_POST
@api_auth(scope="write")
def priority_item_create(request: HttpRequest, year: int, week: int) -> JsonResponse:
    """Create a new priority task and an appearance on the given weeklog."""
    weeklog = get_object_or_404(WeekLog, year=year, week_number=week)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    title = (data.get("title") or "").strip()
    if not title:
        return JsonResponse({"error": "missing_field", "detail": "title is required"}, status=400)
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog,
        title=title[:200],
        priority=data.get("priority", PriorityItem.Priority.MEDIUM),
        status=data.get("status", PriorityItem.Status.NOT_STARTED),
        notes=(data.get("notes") or "")[:2000],
    )
    PriorityItemAppearance.objects.create(
        priority_item=item,
        weeklog=weeklog,
        description=(data.get("description") or "")[:5000],
    )
    return JsonResponse({"priority_item": serialize_priority_item(item)}, status=201)


@require_http_methods(["PATCH"])
@api_auth(scope="write")
def priority_item_update(request: HttpRequest, item_id: int) -> JsonResponse:
    """Patch the long-lived priority item.

    Updating title/priority/status/notes touches the task itself.
    Reopening (status going from completed to anything else) auto-adds
    the task to the current ISO-week weeklog and resets last_active_at.
    """
    item = get_object_or_404(PriorityItem, pk=item_id)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    was_completed = item.status == PriorityItem.Status.COMPLETED
    for field in ("title", "priority", "status", "notes"):
        if field in data:
            value = data[field]
            if field in {"title", "notes"} and isinstance(value, str):
                value = value.strip()[: 200 if field == "title" else 2000]
            setattr(item, field, value)
    item.touch(save=False)
    item.save()
    if was_completed and item.status != PriorityItem.Status.COMPLETED:
        current = WeekLog.get_current_week()
        if current is not None:
            item.reopen(into_weeklog=current)
    return JsonResponse({"priority_item": serialize_priority_item(item)})


@require_POST
@api_auth(scope="write")
def priority_item_merge(
    request: HttpRequest, loser_id: int, winner_id: int
) -> JsonResponse:
    """Merge ``loser_id`` into ``winner_id``.

    Both tasks must be active. Returns the winner's serialized state
    after the merge. The loser is gone — its appearances live on
    ``winner.appearances`` now, with same-week conflicts merged.
    """
    loser = get_object_or_404(PriorityItem, pk=loser_id)
    winner = get_object_or_404(PriorityItem, pk=winner_id)
    try:
        loser.merge_into(winner)
    except ValueError as exc:
        return JsonResponse(
            {"error": "merge_refused", "detail": str(exc)}, status=400
        )
    winner.refresh_from_db()
    return JsonResponse({"priority_item": serialize_priority_item(winner)})


@require_GET
@api_auth(scope="read")
def priority_item_history(request: HttpRequest, item_id: int) -> JsonResponse:
    """All appearances of a single priority task across weeks."""
    item = get_object_or_404(PriorityItem, pk=item_id)
    appearances = (
        item.appearances.select_related("weeklog")
        .order_by("-weeklog__year", "-weeklog__week_number")
    )
    return JsonResponse(
        {
            "priority_item": serialize_priority_item(item),
            "appearances": [
                serialize_priority_appearance(a, include_item=False)
                for a in appearances
            ],
        }
    )


@require_POST
@api_auth(scope="write")
def weeklog_carry_priorities(request: HttpRequest, year: int, week: int) -> JsonResponse:
    """Carry one or more open priority tasks into the given weeklog.

    Body: ``{"item_ids": [1, 2, 3]}``. Returns the created appearances.
    """
    weeklog = get_object_or_404(WeekLog, year=year, week_number=week)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    item_ids = data.get("item_ids") or []
    if not isinstance(item_ids, list) or not all(isinstance(i, int) for i in item_ids):
        return JsonResponse(
            {"error": "invalid_field", "detail": "item_ids must be a list of integers"},
            status=400,
        )
    added = weeklog.add_existing_priority_items(item_ids)
    return JsonResponse({"added": added}, status=201 if added else 200)


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
        created_by=request.api_user,
    )
    return JsonResponse({"incident": serialize_incident(incident)}, status=201)


# -------------------------------------------------------------------------
# Feature requests / development pipeline
# -------------------------------------------------------------------------


@require_GET
@api_auth(scope="read")
def feature_requests_list(request: HttpRequest) -> JsonResponse:
    """List feature requests, grouped by status. Supports `?status=`,
    `?category=`, `?importance=`, `?q=` filters."""
    qs = FeatureRequest.objects.select_related("submitted_by", "solved_by")
    for field in ("status", "category", "importance"):
        val = request.GET.get(field)
        if val:
            qs = qs.filter(**{field: val})
    q = (request.GET.get("q") or "").strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    qs = qs.order_by("status", "order", "-created_at")[:200]
    return JsonResponse(
        {"feature_requests": [serialize_feature_request(o) for o in qs]}
    )


@require_GET
@api_auth(scope="read")
def feature_request_detail(request: HttpRequest, pk: int) -> JsonResponse:
    obj = get_object_or_404(FeatureRequest, pk=pk)
    return JsonResponse({"feature_request": serialize_feature_request(obj)})


@require_POST
@api_auth(scope="write")
def feature_request_create(request: HttpRequest) -> JsonResponse:
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    title = (data.get("title") or "").strip()
    if not title:
        return JsonResponse({"error": "missing_field", "detail": "title is required"}, status=400)
    obj = FeatureRequest.objects.create(
        title=title[:200],
        description=(data.get("description") or "").strip(),
        category=data.get("category", FeatureRequest.Category.OTHER),
        importance=data.get("importance", FeatureRequest.Importance.MEDIUM),
        triggers_version_bump=bool(data.get("triggers_version_bump", False)),
        submitted_by=getattr(request, "api_user", None),
    )
    return JsonResponse({"feature_request": serialize_feature_request(obj)}, status=201)


@require_http_methods(["PATCH"])
@api_auth(scope="write")
def feature_request_update(request: HttpRequest, pk: int) -> JsonResponse:
    obj = get_object_or_404(FeatureRequest, pk=pk)
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    was_solved = obj.status == FeatureRequest.Status.SOLVED
    for field in (
        "title",
        "description",
        "category",
        "importance",
        "status",
        "triggers_version_bump",
        "resolution_notes",
    ):
        if field in data:
            value = data[field]
            if isinstance(value, str):
                value = value.strip()
            if field == "title":
                value = value[:200] if isinstance(value, str) else value
            setattr(obj, field, value)
    obj.save()
    # Stamp solved_at / solved_by on transition into solved
    if obj.status == FeatureRequest.Status.SOLVED and not was_solved:
        obj.solved_at = timezone.now()
        obj.solved_by = getattr(request, "api_user", None)
        obj.save(update_fields=["solved_at", "solved_by"])
        obj.notify_submitter_solved(actor=obj.solved_by)
    elif obj.status != FeatureRequest.Status.SOLVED and was_solved:
        obj.solved_at = None
        obj.solved_by = None
        obj.save(update_fields=["solved_at", "solved_by"])
    return JsonResponse({"feature_request": serialize_feature_request(obj)})


@require_POST
@api_auth(scope="write")
def feature_request_solve(request: HttpRequest, pk: int) -> JsonResponse:
    obj = get_object_or_404(FeatureRequest, pk=pk)
    obj.mark_solved(by=getattr(request, "api_user", None))
    return JsonResponse({"feature_request": serialize_feature_request(obj)})


# ---------------------------------------------------------------------------
# Reports (0.17.0): standalone HTML pages under "Rapporter".
# ---------------------------------------------------------------------------


def _report_payload(request: HttpRequest, report: Report) -> dict:
    return {
        "slug": report.slug,
        "title": report.title,
        "description": report.description,
        "is_public": report.is_public,
        "public_token": report.public_token,
        "public_url": request.build_absolute_uri(report.get_public_path()),
        "url": request.build_absolute_uri(report.get_absolute_url()),
        "size_bytes": len(report.html.encode("utf-8")),
        "has_video": bool(report.video),
        "video_url": request.build_absolute_uri(report.get_video_path()) if report.video else None,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


@require_GET
@api_auth(scope="read")
def reports_list(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"reports": [_report_payload(request, r) for r in Report.objects.all()]})


@require_http_methods(["PUT"])
@api_auth(scope="write")
def report_upsert(request: HttpRequest, slug: str) -> JsonResponse:
    """Create or replace a report by slug. Body: title (required on create),
    html (required on create), description, is_public. The public token is
    kept across updates so a shared link survives a new version."""
    try:
        body = _parse_json_body(request)
    except ValueError as e:
        return JsonResponse({"error": "invalid_json", "detail": str(e)}, status=400)
    unknown = set(body) - {"title", "html", "description", "is_public"}
    if unknown:
        return JsonResponse({"error": "unknown_fields", "detail": sorted(unknown)}, status=400)
    report = Report.objects.filter(slug=slug).first()
    created = report is None
    if created:
        missing = [f for f in ("title", "html") if not body.get(f)]
        if missing:
            return JsonResponse({"error": "missing_fields", "detail": missing}, status=400)
        report = Report(slug=slug, created_by=request.api_user)
    for field in ("title", "html", "description"):
        if field in body:
            if not isinstance(body[field], str):
                return JsonResponse({"error": "invalid_field", "detail": f"{field} must be a string"}, status=400)
            setattr(report, field, body[field])
    if "is_public" in body:
        if not isinstance(body["is_public"], bool):
            return JsonResponse({"error": "invalid_field", "detail": "is_public must be a boolean"}, status=400)
        report.is_public = body["is_public"]
    report.save()
    return JsonResponse({"report": _report_payload(request, report)}, status=201 if created else 200)


@require_http_methods(["PUT"])
@api_auth(scope="write")
def report_video_upload(request: HttpRequest, slug: str) -> JsonResponse:
    """Attach or replace the report's MP4. Body is the raw file
    (Content-Type: video/mp4). Up to 300 MB."""
    report = Report.objects.filter(slug=slug).first()
    if report is None:
        return JsonResponse({"error": "not_found", "detail": "No report with that slug"}, status=404)
    if not request.content_type.startswith("video/mp4"):
        return JsonResponse({"error": "unsupported_media_type", "detail": "Send the MP4 as the raw body with Content-Type: video/mp4"}, status=415)
    # Stream the body to a temp file: request.body would load it into memory and
    # trip DATA_UPLOAD_MAX_MEMORY_SIZE (2.5 MB) for any real video.
    from django.core.files import File
    from django.core.files.temp import NamedTemporaryFile

    limit = 300 * 1024 * 1024
    tmp = NamedTemporaryFile(suffix=".mp4")
    total = 0
    while True:
        chunk = request.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            return JsonResponse({"error": "too_large", "detail": "Max 300 MB"}, status=413)
        tmp.write(chunk)
    if total == 0:
        return JsonResponse({"error": "empty_body"}, status=400)
    tmp.seek(0)
    if report.video:
        report.video.delete(save=False)
    report.video.save("video.mp4", File(tmp), save=True)
    return JsonResponse({"report": _report_payload(request, report)})


# -------------------------------------------------------------------------
# CVEs (Harbinger, server-to-server)
#
# Unlike the older write endpoints these validate every field, choices
# included, and answer 400 with {"error", "detail"} on bad input.
# -------------------------------------------------------------------------


def _cve_payload(request: HttpRequest, cve: CVE, *, full: bool = False) -> dict:
    url = request.build_absolute_uri(reverse("cves:detail", kwargs={"pk": cve.pk}))
    return serialize_cve(cve, url=url, full=full)


def _invalid(field: str, detail: str) -> JsonResponse:
    return JsonResponse({"error": "invalid_field", "field": field, "detail": detail}, status=400)


class _InputError(Exception):
    """Bad API input; ``response`` is the 400 to send."""

    def __init__(self, response: JsonResponse):
        self.response = response
        super().__init__(response.content.decode())


def _clean_cve_input(data: dict, prefix: str = "") -> dict:
    """Validate one CVE object from a request body.

    Returns ``cve_id`` (normalised), ``subject``, ``cvss``, ``severity``,
    ``cvefeed_url`` and ``source_url``; raises _InputError with a 400
    naming the field (``prefix`` is prepended, e.g. ``cves[2].``).
    """
    def missing(field):
        return _InputError(JsonResponse({"error": "missing_field", "field": prefix + field,
                                         "detail": f"{prefix}{field} is required"}, status=400))

    def invalid(field, detail):
        return _InputError(_invalid(prefix + field, prefix + detail))

    raw_id = data.get("cve_id")
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise missing("cve_id")
    try:
        cve_id = normalise_cve_id(raw_id)
    except ValidationError:
        raise invalid("cve_id", "cve_id must look like CVE-YYYY-NNNN (four or more digits)") from None

    subject = data.get("subject")
    if not isinstance(subject, str) or not subject.strip():
        raise missing("subject")
    subject = subject.strip()
    if len(subject) > 300:
        raise invalid("subject", "subject must be at most 300 characters")

    cvss = data.get("cvss")
    if cvss is not None:
        if isinstance(cvss, bool) or not isinstance(cvss, (int, float)) or not 0 <= cvss <= 10:
            raise invalid("cvss", "cvss must be a number between 0 and 10, or null")
        cvss = round(float(cvss), 1)

    severity = data.get("severity")
    if severity is not None and severity not in CVE.Severity.values:
        raise invalid("severity", f"severity must be one of {', '.join(CVE.Severity.values)}, or null")

    fields = {"cve_id": cve_id, "subject": subject, "cvss": cvss, "severity": severity or ""}
    for field in ("cvefeed_url", "source_url"):
        fields[field] = _clean_url(data.get(field), prefix + field)
    return fields


def _clean_url(value, field: str) -> str:
    if value is None or value == "":
        return ""
    try:
        if not isinstance(value, str):
            raise ValidationError("not a string")
        URLValidator(schemes=["http", "https"])(value)
    except ValidationError:
        raise _InputError(_invalid(field, f"{field} must be an http(s) URL, or null")) from None
    return value


def _create_cve(fields: dict, user) -> CVE:
    return CVE.objects.create(
        **fields,
        source="harbinger" if fields["source_url"] else "api",
        created_by=user,
    )


@require_GET
@api_auth(scope="read")
def cve_list(request: HttpRequest) -> JsonResponse:
    """All CVEs, open ones first. Optional ``?state=identified|patching|solved``."""
    qs = CVE.objects.select_related("case")
    state = request.GET.get("state")
    if state:
        if state not in CVE.State.values:
            return _invalid("state", f"state must be one of {', '.join(CVE.State.values)}")
        qs = qs.filter(state=state)
    return JsonResponse({"cves": [_cve_payload(request, c) for c in qs.open_first()[:500]]})


@api_auth(scope="write")
def cve_create(request: HttpRequest) -> JsonResponse:
    """Create a CVE, or add a comment to the one that already exists.

    201 when created, 200 when it existed (its fields are left untouched).
    The whole body is validated either way, so bad input is always a 400.
    Body: ``cve_id`` and ``subject`` required; ``cvss``, ``severity``,
    ``cvefeed_url``, ``source_url`` and ``comment`` optional.
    """
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)

    try:
        fields = _clean_cve_input(data)
    except _InputError as exc:
        return exc.response
    cve_id = fields["cve_id"]

    comment = data.get("comment")
    if comment is not None and not isinstance(comment, str):
        return _invalid("comment", "comment must be a string or null")
    comment = (comment or "").strip()

    def existing_response(existing: CVE) -> JsonResponse:
        if comment:
            CVEComment.objects.create(cve=existing, text=comment, author=request.api_user)
            existing.refresh_from_db()
        return JsonResponse({**_cve_payload(request, existing), "created": False}, status=200)

    existing = CVE.objects.filter(cve_id=cve_id).first()
    if existing is not None:
        return existing_response(existing)

    try:
        # Atomic so a lost race leaves the outer transaction usable.
        with transaction.atomic():
            cve = _create_cve(fields, request.api_user)
    except IntegrityError:
        # Two senders raced on the same cve_id (e.g. two colleagues pressing
        # "Send to Chronicle" at once): the other request created it first.
        return existing_response(CVE.objects.get(cve_id=cve_id))
    if comment:
        CVEComment.objects.create(cve=cve, text=comment, author=request.api_user)
        cve.refresh_from_db()
    return JsonResponse({**_cve_payload(request, cve), "created": True}, status=201)


@csrf_exempt
def cve_collection(request: HttpRequest) -> JsonResponse:
    """``/api/v1/cves/``: GET lists (read key), POST creates (write key)."""
    if request.method == "GET":
        return cve_list(request)
    if request.method == "POST":
        return cve_create(request)
    return JsonResponse({"error": "method_not_allowed"}, status=405, headers={"Allow": "GET, POST"})


@require_GET
@api_auth(scope="read")
def cve_detail(request: HttpRequest, cve_id: str) -> JsonResponse:
    """One CVE by its id (case-insensitive), with links and comments."""
    cve = CVE.objects.filter(cve_id=cve_id.strip().upper()).first()
    if cve is None:
        return JsonResponse({"error": "not_found", "detail": f"No CVE {cve_id}"}, status=404)
    return JsonResponse(_cve_payload(request, cve, full=True))



# -------------------------------------------------------------------------
# CVE cases (Harbinger): several CVEs with one assessment and one fix
# -------------------------------------------------------------------------

MAX_CASE_CVES = 200


def _case_payload(request: HttpRequest, case: CVECase) -> dict:
    return serialize_case(
        case,
        url=request.build_absolute_uri(case.get_absolute_url()),
        cve_url=lambda c: request.build_absolute_uri(c.get_absolute_url()),
    )


def _optional_text(data: dict, field: str, limit: int | None = None) -> str | None:
    """A string field that may be absent (None), else stripped; 400 on bad type/length."""
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _InputError(_invalid(field, f"{field} must be a string or null"))
    value = value.strip()
    if limit and len(value) > limit:
        raise _InputError(_invalid(field, f"{field} must be at most {limit} characters"))
    return value


@api_auth(scope="write")
def case_upsert(request: HttpRequest) -> JsonResponse:
    """Create a case, or add to an existing one (``id``), with its CVEs.

    Body: ``title`` (required when creating); ``id`` (an existing case);
    ``assessment``, ``solution``, ``source``, ``reference``, ``source_url``,
    ``comment``; ``state``
    and ``resolution`` (patched|not_affected, only with state=solved);
    ``cves``: a list of CVE objects as for POST /cves/ (``cve_id`` and
    ``subject`` required). Unknown CVEs are created; known ones keep their
    fields. A CVE that is already in another case makes it a 409 with
    nothing changed. Text fields given for an existing case replace its
    text; absent ones leave it. 201 when created, 200 when updated.
    """
    try:
        data = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": "invalid_body", "detail": str(exc)}, status=400)
    try:
        case_id = data.get("id")
        if case_id is not None and (isinstance(case_id, bool) or not isinstance(case_id, int)):
            return _invalid("id", "id must be an integer or null")
        title = _optional_text(data, "title", 200)
        if case_id is None and not title:
            return JsonResponse({"error": "missing_field", "field": "title", "detail": "title is required"}, status=400)
        assessment = _optional_text(data, "assessment")
        solution = _optional_text(data, "solution")
        comment = _optional_text(data, "comment") or ""
        source_url = _clean_url(data.get("source_url"), "source_url")
        source = _optional_text(data, "source", 40)
        reference = _optional_text(data, "reference", 100)

        state = data.get("state")
        if state is not None and state not in CVE.State.values:
            return _invalid("state", f"state must be one of {', '.join(CVE.State.values)}, or null")
        resolution = data.get("resolution") or ""
        if resolution and resolution not in CVECase.Resolution.values:
            return _invalid("resolution", f"resolution must be one of {', '.join(CVECase.Resolution.values)}, or null")
        if resolution and state != CVE.State.SOLVED:
            return _invalid("resolution", "resolution only goes with state=solved")

        raw_cves = data.get("cves", [])
        if not isinstance(raw_cves, list):
            return _invalid("cves", "cves must be a list")
        if len(raw_cves) > MAX_CASE_CVES:
            return _invalid("cves", f"at most {MAX_CASE_CVES} CVEs per request")
        inputs, seen = [], set()
        for i, item in enumerate(raw_cves):
            if not isinstance(item, dict):
                return _invalid(f"cves[{i}]", "each CVE must be an object")
            fields = _clean_cve_input(item, prefix=f"cves[{i}].")
            if fields["cve_id"] not in seen:
                seen.add(fields["cve_id"])
                inputs.append(fields)
    except _InputError as exc:
        return exc.response

    case = None
    if case_id is not None:
        case = CVECase.objects.filter(pk=case_id).first()
        if case is None:
            return JsonResponse({"error": "not_found", "detail": f"No case {case_id}"}, status=404)

    existing = {c.cve_id: c for c in CVE.objects.filter(cve_id__in=seen).select_related("case")}
    taken = [c for c in existing.values() if c.case_id and (case is None or c.case_id != case.pk)]
    if taken:
        return JsonResponse({
            "error": "conflict",
            "detail": "Some CVEs are already in another case (a CVE belongs to at most one)",
            "cves": [{"cve_id": c.cve_id, "case_id": c.case_id, "case_title": c.case.title} for c in taken],
        }, status=409)

    user = request.api_user
    created = case is None
    with transaction.atomic():
        if created:
            case = CVECase.objects.create(
                title=title, assessment=assessment or "", solution=solution or "",
                source=source or ("harbinger" if source_url else "api"), reference=reference or "",
                source_url=source_url, created_by=user,
            )
        else:
            changed = []
            for field, value in (("title", title), ("assessment", assessment), ("solution", solution),
                                 ("reference", reference)):
                if value is not None and (value or field != "title") and getattr(case, field) != value:
                    setattr(case, field, value)
                    changed.append(field)
            if source_url and not case.source_url:
                case.source_url, case.source = source_url, source or "harbinger"
                changed += ["source_url", "source"]
            elif source and case.source != source:
                case.source = source
                changed.append("source")
            if changed:
                case.save(update_fields=[*changed, "updated_at"])
        cves = []
        for fields in inputs:
            cve = existing.get(fields["cve_id"])
            if cve is None:
                try:
                    with transaction.atomic():
                        cve = _create_cve(fields, user)
                except IntegrityError:  # created concurrently by a single-CVE push
                    cve = CVE.objects.get(cve_id=fields["cve_id"])
                    if cve.case_id and cve.case_id != case.pk:
                        transaction.set_rollback(True)
                        return JsonResponse({"error": "conflict", "detail": f"{cve.cve_id} joined another case meanwhile"}, status=409)
            cves.append(cve)
        if created:
            # The new case starts in the requested state, so its CVEs join in that state.
            if state:
                case.set_state(state, user, resolution=resolution)
            case.add_cves(cves, user)
        else:
            case.add_cves(cves, user)
            if state:
                case.set_state(state, user, resolution=resolution)
        if comment:
            CVEComment.objects.create(case=case, text=comment, author=user)
    case.refresh_from_db()
    return JsonResponse({**_case_payload(request, case), "created": created}, status=201 if created else 200)


@require_GET
@api_auth(scope="read")
def case_list(request: HttpRequest) -> JsonResponse:
    """All cases, open ones first."""
    qs = CVECase.objects.prefetch_related("cves").open_first()[:500]
    return JsonResponse({"cases": [_case_payload(request, c) for c in qs]})


@csrf_exempt
def case_collection(request: HttpRequest) -> JsonResponse:
    """``/api/v1/cve-cases/``: GET lists (read key), POST creates/extends (write key)."""
    if request.method == "GET":
        return case_list(request)
    if request.method == "POST":
        return case_upsert(request)
    return JsonResponse({"error": "method_not_allowed"}, status=405, headers={"Allow": "GET, POST"})


@require_GET
@api_auth(scope="read")
def case_detail(request: HttpRequest, pk: int) -> JsonResponse:
    case = CVECase.objects.filter(pk=pk).first()
    if case is None:
        return JsonResponse({"error": "not_found", "detail": f"No case {pk}"}, status=404)
    return JsonResponse(_case_payload(request, case))
