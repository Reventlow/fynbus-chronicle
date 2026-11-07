"""Make queued board changes in Planner. **Sync container only.**

Each :class:`~apps.planner.models.PlannerChange` is made with the token of
the editor who made it (:meth:`PlannerAuth.for_user`), never the service
account's, so Planner's history and Purview's audit log show that person.

Every update reads the item first for its current etag (Planner refuses
an update without one), patches only the fields the change is about, and
writes Planner's answer back into the mirror. If the item changed in the
meantime (412), it is read and tried once more.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

from .graph import GraphClient, GraphError, PlannerError
from .linksync import chronicle_state, planner_state, reconcile_task
from .models import PlannerChange, PlannerLink, PlannerPlan, PlannerTask, SyncState
from .sync import task_defaults

logger = logging.getLogger(__name__)

# Planner has 25 label slots, category1 … category25.
LABEL_SLOTS = [f"category{i}" for i in range(1, 26)]


def reference_key(url: str) -> str:
    """Planner keys a task's references by URL, with these characters
    encoded (Graph's plannerExternalReferences rules)."""
    for char, code in (("%", "%25"), (".", "%2E"), (":", "%3A"), ("@", "%40"), ("#", "%23")):
        url = url.replace(char, code)
    return url


def _patch_fresh(graph: GraphClient, path: str, body: dict) -> dict:
    """PATCH with the item's current etag; once more on a 412 race."""
    for attempt in (1, 2):
        current = graph.get(path)
        try:
            return graph.patch(path, body, current.get("@odata.etag", "")) or graph.get(path)
        except GraphError as exc:
            if exc.status != 412 or attempt == 2:
                raise
    raise AssertionError("unreachable")


def store_task(task_json: dict, *, user=None) -> PlannerTask | None:
    """Put one task as Planner returned it into the mirror, and carry its
    state to linked priorities and cases (as ``user``, who made it)."""
    plan = PlannerPlan.objects.filter(id=task_json.get("planId") or settings.PLANNER_PLAN_ID).first()
    if plan is None:
        return None
    bucket_ids = set(plan.buckets.values_list("id", flat=True))
    defaults = task_defaults(task_json, plan, bucket_ids, timezone.now())
    task, _ = PlannerTask.objects.update_or_create(id=task_json["id"], defaults=defaults)
    reconcile_task(task, user=user)
    return task


def ensure_label(graph: GraphClient, plan_id: str, name: str) -> str:
    """The label slot named ``name`` in the plan, naming a free one if needed.

    A slot is free when it has no name and no mirrored card uses it (an
    unnamed label can still be on cards as a bare colour).
    """
    details = graph.get(f"/planner/plans/{plan_id}/details")
    names = details.get("categoryDescriptions") or {}
    for key in LABEL_SLOTS:
        if (names.get(key) or "").strip().lower() == name.strip().lower():
            return key
    used = {k for keys in PlannerTask.objects.filter(plan_id=plan_id).values_list("label_keys", flat=True)
            for k in keys}
    free = next((k for k in LABEL_SLOTS if not names.get(k) and k not in used), None)
    if free is None:
        raise PlannerError(f"Planen har ingen ledig etiket til \"{name}\". Omdøb eller fjern en i Planner.")
    _patch_fresh(graph, f"/planner/plans/{plan_id}/details", {"categoryDescriptions": {free: name}})
    PlannerPlan.objects.filter(id=plan_id).update(labels={**{k: v for k, v in names.items() if v}, free: name})
    return free


def _link_card(graph: GraphClient, task_id: str, data: dict, user=None) -> None:
    """Label the card and add the reference back to Chronicle."""
    task_path = f"/planner/tasks/{task_id}"
    if data.get("label"):
        key = ensure_label(graph, settings.PLANNER_PLAN_ID, data["label"])
        store_task(_patch_fresh(graph, task_path, {"appliedCategories": {key: True}}), user=user)
    _patch_fresh(graph, f"{task_path}/details", {"references": {reference_key(data["url"]): {
        "@odata.type": "microsoft.graph.plannerExternalReference",
        "alias": data["alias"][:255],
        "type": "Other",
    }}})
    store_task(graph.get(task_path), user=user)  # reference count and etag


def _create(graph: GraphClient, change: PlannerChange) -> None:
    """A new card; from "Opret i Planner" also with description, state,
    due date, and the link to the priority or case it came from."""
    data = change.payload
    body = {
        "planId": settings.PLANNER_PLAN_ID,
        "bucketId": data["bucket_id"],
        "title": data["title"],
        "orderHint": " !",  # top of the bucket, as Planner's own "Add task"
    }
    if data.get("percent"):
        body["percentComplete"] = data["percent"]
    if data.get("due"):
        body["dueDateTime"] = f"{data['due']}T12:00:00Z"  # noon UTC: the same day in Denmark
    created = graph.post("/planner/tasks", body)
    change.task_id = created["id"]
    target = data.get("link") or {}
    if target:
        # The link first, so the card's state is in step from the start.
        link, _ = PlannerLink.objects.get_or_create(
            task_id=created["id"], priority_item_id=target.get("priority_item"), case_id=target.get("case"),
            defaults={"task_title": data["title"][:500], "created_by": change.user})
        link.planner_state = planner_state(created.get("percentComplete") or 0)
        link.chronicle_state = chronicle_state(link.target) if link.target else link.planner_state
        link.save(update_fields=["planner_state", "chronicle_state"])
    store_task(created, user=change.user)
    if data.get("description"):
        _patch_fresh(graph, f"/planner/tasks/{created['id']}/details", {"description": data["description"]})
        PlannerTask.objects.filter(id=created["id"]).update(
            description=data["description"][:4000], has_description=True)
    if target:
        _link_card(graph, created["id"], data, user=change.user)


def apply_change(graph: GraphClient, change: PlannerChange) -> None:
    """Make one change in Planner and mirror the result. Raises PlannerError."""
    kind, data, user = change.kind, change.payload, change.user
    task_path = f"/planner/tasks/{change.task_id}"
    if kind in (PlannerChange.Kind.COMPLETE, PlannerChange.Kind.REOPEN):
        done = kind == PlannerChange.Kind.COMPLETE
        store_task(_patch_fresh(graph, task_path, {"percentComplete": 100 if done else 0}), user=user)
    elif kind == PlannerChange.Kind.PROGRESS:
        store_task(_patch_fresh(graph, task_path, {"percentComplete": int(data["percent"])}), user=user)
    elif kind == PlannerChange.Kind.MOVE:
        body = {"bucketId": data["bucket_id"]}
        if data.get("order_hint"):
            body["orderHint"] = data["order_hint"]
        store_task(_patch_fresh(graph, task_path, body), user=user)
    elif kind == PlannerChange.Kind.CREATE:
        _create(graph, change)
    elif kind == PlannerChange.Kind.LINK:
        _link_card(graph, change.task_id, data, user=user)
    else:
        raise PlannerError(f"Ukendt ændring: {kind}")


def explain(exc: PlannerError) -> str:
    """A message for the editor; Graph's 403 here means no access to the plan."""
    if isinstance(exc, GraphError):
        if exc.status == 403:
            return "Microsoft nægtede ændringen. Er du medlem af planens gruppe i Planner?"
        if exc.status == 404:
            return "Kortet findes ikke længere i Planner."
    return str(exc)


def process_changes(auth_factory, graph_factory) -> int:
    """Make every pending change, oldest first. Returns how many were handled.

    A failed change leaves the board showing what it optimistically showed,
    so a sync is requested to put the mirror back to Planner's state.
    """
    handled = 0
    graphs: dict[int, GraphClient | PlannerError] = {}
    for change in PlannerChange.objects.filter(status=PlannerChange.Status.PENDING).select_related("user"):
        if change.user_id not in graphs:
            try:
                auth = auth_factory.for_user(change.user)
                graphs[change.user_id] = graph_factory(auth.access_token)
            except PlannerError as exc:
                graphs[change.user_id] = exc
        graph = graphs[change.user_id]
        try:
            if isinstance(graph, PlannerError):
                raise graph
            apply_change(graph, change)
            change.status, change.message = PlannerChange.Status.DONE, ""
            logger.info("Planner change %s %s by %s", change.kind, change.task_id, change.user)
        except PlannerError as exc:
            change.status, change.message = PlannerChange.Status.FAILED, explain(exc)[:500]
            logger.warning("Planner change %s failed: %s", change.pk, exc)
        except Exception:
            change.status = PlannerChange.Status.FAILED
            change.message = "Uventet fejl. Se sync-containerens log."
            logger.exception("Planner change %s failed", change.pk)
        change.handled_at = timezone.now()
        change.save(update_fields=["status", "message", "handled_at", "task_id"])
        if change.status == PlannerChange.Status.FAILED:
            SyncState.get()
            SyncState.objects.filter(pk=1).update(requested_at=timezone.now())
        handled += 1
    return handled
