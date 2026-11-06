"""Mirror one Planner plan into Chronicle. **Sync container only.**

:func:`mirror_plan` reads the plan, its buckets, tasks and (where needed)
task details through Graph and makes the local tables match. Planner is
the source of truth: tasks and buckets that are gone there are removed
here. Nothing is written to Planner.

:class:`PlannerJob` is what ``run_scheduler`` drives: every few seconds it
hands over pending sign-ins and picks up "Synk nu" requests, and it runs
the mirror on the schedule from :mod:`apps.planner.schedule`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import schedule
from .graph import GraphClient, PlannerAuth, PlannerError
from .models import (
    DESCRIPTION_MAX,
    PendingSignIn,
    PlannerBucket,
    PlannerPerson,
    PlannerPlan,
    PlannerTask,
    SyncState,
)

logger = logging.getLogger(__name__)

# Task details (the description) are fetched when a task changes, and all
# of them again this often, since a description edit alone may not change
# the task's own etag.
FULL_DETAILS_EVERY = timedelta(hours=1)
# Two "Synk nu" clicks closer than this become one run.
REQUEST_COOLDOWN = timedelta(seconds=30)


def _dt(value: str | None) -> datetime | None:
    return parse_datetime(value) if value else None


def _date(value: str | None) -> date | None:
    """Planner sends due dates as midnight UTC of the chosen day."""
    parsed = _dt(value)
    return parsed.date() if parsed else None


def mirror_plan(graph: GraphClient, plan_id: str, *, full_details: bool = False) -> dict:
    """Make the local mirror match Planner. Returns counts for the status line."""
    now = timezone.now()
    plan_json = graph.get(f"/planner/plans/{plan_id}")
    details_json = graph.get(f"/planner/plans/{plan_id}/details")
    labels = {k: v for k, v in (details_json.get("categoryDescriptions") or {}).items()
              if k.startswith("category") and v}
    buckets = list(graph.get_all(f"/planner/plans/{plan_id}/buckets"))
    tasks = list(graph.get_all(f"/planner/plans/{plan_id}/tasks"))

    existing = {t.id: t for t in PlannerTask.objects.filter(plan_id=plan_id)}
    need_details = [
        t["id"] for t in tasks
        if t.get("hasDescription") and (
            full_details
            or t["id"] not in existing
            or existing[t["id"]].etag != t.get("@odata.etag", "")
            or existing[t["id"]].details_synced_at is None
        )
    ]
    descriptions = {}
    for task_id in need_details:
        d = graph.get(f"/planner/tasks/{task_id}/details")
        descriptions[task_id] = ((d.get("description") or "")[:DESCRIPTION_MAX], d.get("@odata.etag", ""))

    people = {uid for t in tasks for uid in (t.get("assignments") or {})}
    known = set(PlannerPerson.objects.filter(id__in=people).values_list("id", flat=True))
    names = {}
    for uid in people - known:
        try:
            names[uid] = graph.get(f"/users/{uid}", {"$select": "id,displayName"}).get("displayName") or "Ukendt"
        except PlannerError:
            names[uid] = "Ukendt bruger"

    with transaction.atomic():
        plan, _ = PlannerPlan.objects.update_or_create(
            id=plan_id, defaults={"title": plan_json.get("title", ""), "labels": labels, "synced_at": now})
        for uid, name in names.items():
            PlannerPerson.objects.update_or_create(id=uid, defaults={"display_name": name, "looked_up_at": now})

        bucket_ids = set()
        for b in buckets:
            bucket_ids.add(b["id"])
            PlannerBucket.objects.update_or_create(
                id=b["id"], defaults={"plan": plan, "name": b.get("name", ""), "order_hint": b.get("orderHint", "")})
        PlannerBucket.objects.filter(plan=plan).exclude(id__in=bucket_ids).delete()

        task_ids = set()
        for t in tasks:
            task_ids.add(t["id"])
            defaults = {
                "plan": plan,
                "bucket_id": t.get("bucketId") if t.get("bucketId") in bucket_ids else None,
                "title": (t.get("title") or "")[:500],
                "percent_complete": t.get("percentComplete") or 0,
                "priority": t.get("priority", 5),
                "start_date": _date(t.get("startDateTime")),
                "due_date": _date(t.get("dueDateTime")),
                "created_at": _dt(t.get("createdDateTime")),
                "completed_at": _dt(t.get("completedDateTime")),
                "order_hint": t.get("orderHint", ""),
                "assignee_ids": sorted((t.get("assignments") or {}).keys()),
                "label_keys": sorted(k for k, on in (t.get("appliedCategories") or {}).items() if on),
                "checklist_total": t.get("checklistItemCount") or 0,
                "checklist_open": t.get("activeChecklistItemCount") or 0,
                "reference_count": t.get("referenceCount") or 0,
                "has_description": bool(t.get("hasDescription")),
                "etag": t.get("@odata.etag", ""),
                "synced_at": now,
            }
            if t["id"] in descriptions:
                defaults["description"], defaults["details_etag"] = descriptions[t["id"]]
                defaults["details_synced_at"] = now
            elif not t.get("hasDescription"):
                defaults["description"] = ""
            PlannerTask.objects.update_or_create(id=t["id"], defaults=defaults)
        removed, _ = PlannerTask.objects.filter(plan=plan).exclude(id__in=task_ids).delete()

    return {"buckets": len(buckets), "tasks": len(tasks), "details": len(descriptions), "removed": removed}


class PlannerJob:
    """The Planner part of ``run_scheduler``."""

    name = "planner"

    def __init__(self, auth_factory=PlannerAuth, graph_factory=GraphClient):
        self.auth_factory = auth_factory
        self.graph_factory = graph_factory

    @staticmethod
    def enabled() -> bool:
        return bool(settings.PLANNER_SYNC_ENABLED and settings.PLANNER_PLAN_ID)

    def tick(self, now: datetime | None = None) -> None:
        """Called every few seconds: sign-ins, requests, schedule."""
        now = now or timezone.now()
        self.handle_sign_ins()
        state = SyncState.get()
        due = state.next_due_at is None or now >= state.next_due_at
        requested = state.is_requested and (
            state.last_attempt_at is None or now - state.last_attempt_at >= REQUEST_COOLDOWN)
        if due or requested:
            self.run(state, now)

    def handle_sign_ins(self) -> None:
        for pending in PendingSignIn.objects.filter(status=PendingSignIn.Status.PENDING).order_by("created_at"):
            try:
                self.auth_factory().redeem(pending)
            except PlannerError as exc:  # misconfigured sync container
                pending.status, pending.message, pending.sealed = PendingSignIn.Status.FAILED, str(exc)[:500], ""
                pending.handled_at = timezone.now()
                pending.save()
            if pending.status == PendingSignIn.Status.DONE:
                # Sync right away, and drop the "not connected" error from
                # runs before the connection existed.
                SyncState.get()
                SyncState.objects.filter(pk=1).update(next_due_at=timezone.now(), last_error="")

    def run(self, state: SyncState, now: datetime) -> None:
        state.last_attempt_at = now
        state.running_since = now
        state.save(update_fields=["last_attempt_at", "running_since"])
        full = state.last_full_details_at is None or now - state.last_full_details_at >= FULL_DETAILS_EVERY
        try:
            auth = self.auth_factory()
            graph = self.graph_factory(auth.access_token)
            counts = mirror_plan(graph, settings.PLANNER_PLAN_ID, full_details=full)
            state.last_success_at = timezone.now()
            state.last_error = ""
            state.last_counts = counts
            if full:
                state.last_full_details_at = now
            logger.info("Planner sync: %s", counts)
        except PlannerError as exc:
            state.last_error = str(exc)[:500]
            logger.warning("Planner sync failed: %s", exc)
        except Exception:
            state.last_error = "Uventet fejl under synkronisering. Se sync-containerens log."
            logger.exception("Planner sync failed")
        finally:
            state.running_since = None
            state.next_due_at = timezone.now() + timedelta(seconds=schedule.interval_for(timezone.now()))
            state.save()
