"""Two-way status sync between linked Planner cards and Chronicle.

A Planner card has three states that matter here (percentComplete 0, in
between, 100). They map onto a priority's status and a case's state:

==============  =====================  ===========================
Planner         Prioriteret opgave     Sag
==============  =====================  ===========================
not_started     Ikke startet           Identificeret / Planlagt
in_progress     Igangværende/Blokeret  Patcher / I gang
done            Afsluttet              Færdigbehandlet / Udført
==============  =====================  ===========================

Each :class:`~apps.planner.models.PlannerLink` remembers the state each
side had when they were last in step, so a change is only ever carried
from the side that moved:

* **Planner → Chronicle** (:func:`reconcile_task`, sync container): after
  the mirror or a board change has stored Planner's answer, a card whose
  state differs from ``link.planner_state`` updates the priority or case.
* **Chronicle → Planner** (:func:`chronicle_changed`, a post_save signal,
  either container): a priority or case whose state differs from
  ``link.chronicle_state`` queues a ``progress`` change, made in Planner
  with the *acting user's* own connection. Without a user (e.g. the
  6-week auto-close) or without their connection nothing is sent, and the
  link says why (``sync_note``); there is no fallback to the service
  account.

While Planner's state is being applied, :data:`_from_planner` is set so
the resulting save isn't sent straight back.
"""

from __future__ import annotations

import contextvars
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import PlannerChange, PlannerLink, PlannerTask, PlannerUserConnection

logger = logging.getLogger(__name__)

NOT_STARTED, IN_PROGRESS, DONE = "not_started", "in_progress", "done"
PERCENT = {NOT_STARTED: 0, IN_PROGRESS: 50, DONE: 100}

_from_planner: contextvars.ContextVar[bool] = contextvars.ContextVar("planner_from_planner", default=False)
_request: contextvars.ContextVar = contextvars.ContextVar("planner_request", default=None)


# --- who is acting -----------------------------------------------------------------


class CurrentRequestMiddleware:
    """Remembers the request so a save deep in a model method knows who
    made it (the session user, or the owner of an API key)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _request.set(request)
        try:
            return self.get_response(request)
        finally:
            _request.reset(token)


def current_user():
    request = _request.get()
    if request is None:
        return None
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user
    return getattr(request, "api_user", None)


# --- states --------------------------------------------------------------------------


def planner_state(percent: int) -> str:
    if percent >= 100:
        return DONE
    return IN_PROGRESS if percent > 0 else NOT_STARTED


def chronicle_state(obj) -> str:
    """The state of a priority (``status``) or case (``state``)."""
    if getattr(obj, "is_case", False):
        return {"identified": NOT_STARTED, "solved": DONE}.get(obj.state, IN_PROGRESS)
    return {"not_started": NOT_STARTED, "completed": DONE}.get(obj.status, IN_PROGRESS)


def apply_to_chronicle(obj, state: str, *, user=None, card_title: str = "") -> None:
    """Move a priority or case to the Planner state (without echoing it)."""
    if chronicle_state(obj) == state:
        return
    token = _from_planner.set(True)
    try:
        if getattr(obj, "is_case", False):
            target = {NOT_STARTED: "identified", IN_PROGRESS: "patching", DONE: "solved"}[state]
            if obj.set_state(target, user):
                obj._log(f"Ændret i Planner (kortet »{card_title}«).", user, state=False)
        else:
            _apply_to_priority(obj, state)
    finally:
        _from_planner.reset(token)


def _apply_to_priority(item, state: str) -> None:
    from apps.logbook.models import PriorityItem, WeekLog

    if state == DONE:
        item.status = PriorityItem.Status.COMPLETED
        item.closed_at = timezone.now()
        item.last_active_at = timezone.now()
        item.save(update_fields=["status", "closed_at", "last_active_at", "updated_at"])
        return
    if item.status == PriorityItem.Status.COMPLETED:
        # As when reopened in Chronicle: back on this week's log.
        item.reopen(into_weeklog=WeekLog.get_current_week())
    item.status = PriorityItem.Status.NOT_STARTED if state == NOT_STARTED else PriorityItem.Status.ONGOING
    item.last_active_at = timezone.now()
    item.save(update_fields=["status", "last_active_at", "updated_at"])


# --- Planner → Chronicle ---------------------------------------------------------------


def reconcile_task(task: PlannerTask, *, user=None) -> int:
    """Carry a card's state to its linked priorities and cases if Planner
    moved since they were last in step. Returns how many were changed."""
    changed = 0
    p_state = planner_state(task.percent_complete)
    for link in PlannerLink.objects.filter(task_id=task.id).select_related("priority_item", "case"):
        target = link.target
        if target is None or (link.priority_item_id and link.priority_item.is_deleted):
            continue
        if not link.planner_state:  # first time seen: just note where both are
            link.planner_state, link.chronicle_state = p_state, chronicle_state(target)
            link.save(update_fields=["planner_state", "chronicle_state"])
            continue
        if link.planner_state == p_state:
            continue
        with transaction.atomic():
            before = chronicle_state(target)
            apply_to_chronicle(target, p_state, user=user, card_title=task.title)
            link.planner_state, link.chronicle_state = p_state, chronicle_state(target)
            link.sync_note = ""
            link.save(update_fields=["planner_state", "chronicle_state", "sync_note"])
        if link.chronicle_state != before:
            changed += 1
            logger.info("Planner card %s → %s %s", task.id, link.target_label, p_state)
    return changed


def reconcile_plan(plan_id: str) -> int:
    """After a mirror run: every linked card in the plan."""
    linked = set(PlannerLink.objects.values_list("task_id", flat=True))
    return sum(reconcile_task(t) for t in PlannerTask.objects.filter(plan_id=plan_id, id__in=linked))


# --- Chronicle → Planner ---------------------------------------------------------------


def chronicle_changed(obj) -> None:
    """A priority or case was saved: queue its new state for linked cards."""
    if not settings.PLANNER_ENABLED or _from_planner.get() or obj.pk is None:
        return
    field = "case" if getattr(obj, "is_case", False) else "priority_item"
    links = list(PlannerLink.objects.filter(**{field: obj}))
    if not links:
        return
    c_state = chronicle_state(obj)
    user = current_user()
    for link in links:
        if not link.planner_state or link.chronicle_state == c_state:
            continue
        link.chronicle_state = c_state
        if link.planner_state == c_state:
            link.sync_note = ""  # already so in Planner
        elif not settings.PLANNER_WRITES_ENABLED:
            link.sync_note = "Ikke sendt til Planner: ændringer i Planner er slået fra."
        elif user is None:
            link.sync_note = "Ændret i Chronicle uden en bruger (fx auto-luk); ikke sendt til Planner."
        elif not PlannerUserConnection.objects.filter(user=user).exclude(sealed_token_cache="").exists():
            name = user.get_full_name() or user.get_username()
            link.sync_note = f"Ikke sendt til Planner: {name} har ikke forbundet sin Microsoft-konto."
        else:
            PlannerChange.objects.create(kind=PlannerChange.Kind.PROGRESS, task_id=link.task_id, user=user,
                                         payload={"percent": PERCENT[c_state]})
            link.sync_note = ""
        link.save(update_fields=["chronicle_state", "sync_note"])
