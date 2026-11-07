"""Planner board views. **Web container: never calls Microsoft Graph.**

The board renders the local mirror. "Synk nu" only records a request for
the sync container, and so does every change on the board (complete,
reopen, move, add, link): it becomes a :class:`PlannerChange` that the
sync container makes in Planner with the editor's own sign-in. The board
shows the change straight away and the card polls until it is done.

Connecting an account sends the person to Microsoft (the URL needs the
client id, not the secret); Microsoft's code comes back here and is sealed
straight away for the sync container, which alone can open and redeem it.

Who may do what:
* the board, its status and "Synk nu": editors (not the read-only Viewer
  group), since the plan is internal IT work;
* changes: editors who have connected their own Microsoft account;
* connecting or disconnecting the service account: staff.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from functools import wraps
from itertools import groupby

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from apps.accounts.permissions import is_editor
from apps.cves.models import CVECase
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog

from . import crypto
from .graph import authorize_url
from .models import (
    PendingSignIn,
    PlannerBucket,
    PlannerChange,
    PlannerConnection,
    PlannerLink,
    PlannerPerson,
    PlannerPlan,
    PlannerTask,
    PlannerUserConnection,
    SyncState,
    task_url,
)
from .schedule import interval_for

SESSION_KEY = "planner_connect"

# Planner's 25 label colours (category1..category25), approximated.
LABEL_COLORS = [
    "#e8478b", "#d13438", "#c19c00", "#498205", "#0078d4", "#8764b8", "#a67c52", "#8cbd18",
    "#00b7c3", "#69797e", "#8a8886", "#8e562e", "#c50f1f", "#f7630c", "#ff8c00", "#eaa300",
    "#13a10e", "#0b6a0b", "#038387", "#3a96dd", "#004e8c", "#8378de", "#5c2e91", "#a19f9d",
    "#3b3a39",
]


def board_access(view):
    """Logged in, Planner enabled, and an editor."""
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.PLANNER_ENABLED:
            raise Http404
        if not is_editor(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def staff_only(view):
    @board_access
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def plan_url() -> str:
    return (f"https://planner.cloud.microsoft/ui/web/plan/{settings.PLANNER_PLAN_ID}"
            f"/view/board?tid={settings.PLANNER_TENANT_ID}")


def _status_context(request: HttpRequest) -> dict:
    state = SyncState.get()
    conn = PlannerConnection.get()
    now = timezone.now()
    pending = PendingSignIn.objects.filter(status=PendingSignIn.Status.PENDING).exists()
    # Stale: no success for three scheduled intervals (plus the run itself).
    stale_after = 3 * interval_for(now) + 60
    stale = bool(conn.is_connected and (
        not state.last_success_at or (now - state.last_success_at).total_seconds() > stale_after))
    busy = bool(state.is_requested or state.running_since or pending)
    return {
        "state": state,
        "connection": conn,
        "pending_sign_in": pending,
        "stale": stale,
        "busy": busy,
        "since": request.GET.get("since", ""),
    }


def user_connection(user) -> PlannerUserConnection | None:
    return PlannerUserConnection.objects.filter(user=user).first()


def can_write(user) -> bool:
    """Changes need writes switched on and the editor's own connection."""
    if not settings.PLANNER_WRITES_ENABLED:
        return False
    conn = user_connection(user)
    return bool(conn and conn.is_connected)


def decorate(tasks: list[PlannerTask], plan: PlannerPlan) -> list[PlannerTask]:
    """Add what a card shows besides the task itself: people, labels,
    links to Chronicle and a change still on its way to Planner."""
    ids = [t.id for t in tasks]
    people = {p.id: p for p in PlannerPerson.objects.filter(
        id__in={i for t in tasks for i in t.assignee_ids})}
    links: dict[str, list[PlannerLink]] = {}
    for link in PlannerLink.objects.filter(task_id__in=ids).select_related("priority_item", "case"):
        links.setdefault(link.task_id, []).append(link)
    pending = {c.task_id: c for c in PlannerChange.objects.filter(
        task_id__in=ids, status=PlannerChange.Status.PENDING)}
    for task in tasks:
        task.people = [people[i] for i in task.assignee_ids if i in people]
        task.labels = [
            {"name": plan.labels[k], "color": LABEL_COLORS[(int(k[8:]) - 1) % 25]}
            for k in task.label_keys if k in plan.labels
        ]
        task.links = links.get(task.id, [])
        task.change = pending.get(task.id)
        task.planner_url = task_url(task.id)
    return tasks


def _buckets(plan: PlannerPlan | None) -> list[PlannerBucket]:
    # Planner lays buckets out by descending order hint (cards within a
    # bucket ascending); checked against the live board in 1.16.1.
    return list(PlannerBucket.objects.filter(plan=plan).order_by("-order_hint")) if plan else []


def _card_context(request: HttpRequest, task: PlannerTask, **extra) -> dict:
    plan = task.plan
    decorate([task], plan)
    return {"task": task, "buckets": _buckets(plan), "can_write": can_write(request.user), **extra}


@board_access
def board(request: HttpRequest) -> HttpResponse:
    plan = PlannerPlan.objects.filter(id=settings.PLANNER_PLAN_ID).first()
    columns = []
    buckets = _buckets(plan)
    if plan:
        tasks = decorate(list(PlannerTask.objects.filter(plan=plan).select_related("bucket")), plan)
        by_bucket = {key: list(group) for key, group in
                     groupby(sorted(tasks, key=lambda t: (t.bucket_id or "", t.order_hint)),
                             key=lambda t: t.bucket_id or "")}
        for bucket in buckets:
            in_bucket = by_bucket.get(bucket.id, [])
            columns.append({
                "bucket": bucket,
                "open": [t for t in in_bucket if not t.is_complete],
                "done": sorted((t for t in in_bucket if t.is_complete),
                               key=lambda t: t.completed_at or timezone.now(), reverse=True),
            })
    ctx = _status_context(request)
    ctx.update({
        "plan": plan,
        "columns": columns,
        "plan_url": plan_url(),
        "can_connect": request.user.is_staff,
        "connect_configured": bool(settings.PLANNER_CLIENT_ID and crypto.can_seal()),
        "since": ctx["state"].last_success_at.isoformat() if ctx["state"].last_success_at else "",
        "buckets": buckets,
        "writes_enabled": settings.PLANNER_WRITES_ENABLED,
        "can_write": can_write(request.user),
        "my_connection": user_connection(request.user),
        "my_sign_in_pending": PendingSignIn.objects.filter(
            for_user=request.user, status=PendingSignIn.Status.PENDING).exists(),
    })
    return render(request, "planner/board.html", ctx)


@board_access
def status(request: HttpRequest) -> HttpResponse:
    """The sync line; reloads the page once a newer sync has landed."""
    ctx = _status_context(request)
    since = parse_datetime(ctx["since"]) if ctx["since"] else None
    landed = ctx["state"].last_success_at
    if landed and (since is None or landed > since) and not ctx["busy"]:
        response = HttpResponse()
        response["HX-Refresh"] = "true"
        return response
    return render(request, "planner/partials/status.html", ctx)


@board_access
@require_POST
def sync_now(request: HttpRequest) -> HttpResponse:
    state = SyncState.get()
    state.requested_at = timezone.now()
    state.requested_by = request.user
    state.save(update_fields=["requested_at", "requested_by"])
    ctx = _status_context(request)
    return render(request, "planner/partials/status.html", ctx)


def _redirect_uri(request: HttpRequest) -> str:
    return settings.PLANNER_REDIRECT_URI or request.build_absolute_uri(reverse("planner:connect-callback"))


def _start_sign_in(request: HttpRequest, *, personal: bool) -> HttpResponse:
    """PKCE + state in the session, then off to Microsoft."""
    if not (settings.PLANNER_CLIENT_ID and crypto.can_seal()):
        messages.error(request, "Planner-forbindelsen er ikke sat op (PLANNER_CLIENT_ID / PLANNER_PUBLIC_KEY).")
        return redirect("planner:board")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect_uri = _redirect_uri(request)
    request.session[SESSION_KEY] = {"state": state, "verifier": verifier, "redirect_uri": redirect_uri,
                                    "personal": personal}
    hint = (request.user.email or "") if personal else None
    return redirect(authorize_url(state=state, code_challenge=challenge, redirect_uri=redirect_uri,
                                  login_hint=hint))


@staff_only
@require_POST
def connect(request: HttpRequest) -> HttpResponse:
    """Send a staff member to Microsoft to sign in as the service account."""
    return _start_sign_in(request, personal=False)


@board_access
@require_POST
def connect_me(request: HttpRequest) -> HttpResponse:
    """Send an editor to Microsoft to connect their own account."""
    if not settings.PLANNER_WRITES_ENABLED:
        raise PermissionDenied
    return _start_sign_in(request, personal=True)


@board_access
def connect_callback(request: HttpRequest) -> HttpResponse:
    """Microsoft returns here (both flows); seal the code for the sync container."""
    flow = request.session.pop(SESSION_KEY, None)
    if not flow or not secrets.compare_digest(request.GET.get("state", ""), flow["state"]):
        messages.error(request, "Login-forsøget kunne ikke genkendes. Start forbindelsen igen.")
        return redirect("planner:board")
    personal = bool(flow.get("personal"))
    if not personal and not request.user.is_staff:
        raise PermissionDenied
    if request.GET.get("error"):
        messages.error(request, f"Microsoft afbrød login: {request.GET.get('error_description') or request.GET['error']}"[:300])
        return redirect("planner:board")
    code = request.GET.get("code", "")
    if not code:
        messages.error(request, "Microsoft sendte ingen login-kode.")
        return redirect("planner:board")
    PendingSignIn.objects.create(
        sealed=crypto.seal({"code": code, "code_verifier": flow["verifier"],
                            "redirect_uri": flow["redirect_uri"]}),
        created_by=request.user,
        for_user=request.user if personal else None,
    )
    messages.info(request, "Login modtaget. Synkroniseringen forbinder kontoen om få sekunder.")
    return redirect("planner:board")


@staff_only
@require_POST
def disconnect(request: HttpRequest) -> HttpResponse:
    conn = PlannerConnection.get()
    conn.sealed_token_cache = ""
    conn.home_account_id = ""
    conn.last_error = "Afbrudt af " + request.user.get_username()
    conn.save()
    messages.info(request, "Planner-forbindelsen er afbrudt. Tavlen viser den seneste kopi, til den forbindes igen.")
    return redirect("planner:board")


@board_access
@require_POST
def disconnect_me(request: HttpRequest) -> HttpResponse:
    """Forget the editor's own tokens; the board turns read-only for them."""
    PlannerUserConnection.objects.filter(user=request.user).update(
        sealed_token_cache="", home_account_id="", last_error="")
    messages.info(request, "Din Microsoft-konto er ikke længere forbundet til Planner.")
    return redirect("planner:board")


# --- changes on the board ---------------------------------------------------------


def write_access(view):
    """An editor with their own connection; the task (if any) must be in
    the mirrored plan."""
    @board_access
    @require_POST
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_write(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def _task(task_id: str) -> PlannerTask:
    return get_object_or_404(PlannerTask.objects.select_related("plan"), id=task_id,
                             plan_id=settings.PLANNER_PLAN_ID)


def _queue(request: HttpRequest, kind: str, task_id: str = "", **payload) -> PlannerChange:
    return PlannerChange.objects.create(kind=kind, task_id=task_id, payload=payload, user=request.user)


def _render_card(request: HttpRequest, task: PlannerTask, **extra) -> HttpResponse:
    return render(request, "planner/partials/card.html", _card_context(request, task, **extra))


@write_access
def complete(request: HttpRequest, task_id: str) -> HttpResponse:
    """Tick or untick a card (``done=1`` / ``done=0``)."""
    task = _task(task_id)
    done = request.POST.get("done") == "1"
    task.percent_complete = 100 if done else 0
    task.completed_at = timezone.now() if done else None
    task.save(update_fields=["percent_complete", "completed_at"])
    _queue(request, PlannerChange.Kind.COMPLETE if done else PlannerChange.Kind.REOPEN, task.id)
    return _render_card(request, task)


def order_hint_between(prev: str, nxt: str) -> str:
    """Planner computes a hint between two neighbours from ``"<prev> <next>!"``
    (either may be empty at the ends of the bucket; ``" !"`` is the top)."""
    return f"{prev} {nxt}!"


@write_access
def move(request: HttpRequest, task_id: str) -> HttpResponse:
    """Move a card to a bucket (dragged there, or picked from its menu)."""
    task = _task(task_id)
    bucket = get_object_or_404(PlannerBucket, id=request.POST.get("bucket", ""), plan_id=task.plan_id)
    from_menu = bool(request.POST.get("from_menu"))
    if from_menu and task.bucket_id == bucket.id:
        return _render_card(request, task)
    # Dragged: between its new neighbours. From the menu: top of the bucket.
    hint = order_hint_between(request.POST.get("prev", ""), request.POST.get("next", ""))
    task.bucket = bucket
    task.save(update_fields=["bucket"])
    _queue(request, PlannerChange.Kind.MOVE, task.id, bucket_id=bucket.id, order_hint=hint)
    response = _render_card(request, task)
    if from_menu:
        response["HX-Refresh"] = "true"  # the card has to change column
    return response


@write_access
def create(request: HttpRequest, bucket_id: str) -> HttpResponse:
    """A new card at the top of a bucket; shown as a placeholder until made."""
    bucket = get_object_or_404(PlannerBucket, id=bucket_id, plan_id=settings.PLANNER_PLAN_ID)
    title = " ".join(request.POST.get("title", "").split())[:255]
    if not title:
        return HttpResponse(status=204)
    change = _queue(request, PlannerChange.Kind.CREATE, bucket_id=bucket.id, title=title)
    return render(request, "planner/partials/new_card.html", {"change": change})


def _link_targets() -> dict:
    return {
        "priorities": PriorityItem.objects.active().exclude(status=PriorityItem.Status.COMPLETED)
                                          .order_by("title")[:300],
        "cases": CVECase.objects.open().order_by("-updated_at")[:300],
    }


def _priority_from(task: PlannerTask, user) -> PriorityItem:
    """A priority item for this week, with what the card knows."""
    weeklog = WeekLog.get_or_create_current_week(user)
    level = (PriorityItem.Priority.HIGH if task.priority <= 4
             else PriorityItem.Priority.MEDIUM if task.priority <= 7 else PriorityItem.Priority.LOW)
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog, title=task.title[:200], priority=level,
        status=PriorityItem.Status.ONGOING if task.is_in_progress else PriorityItem.Status.NOT_STARTED,
        notes=task.description[:2000],
    )
    last = weeklog.priority_appearances.aggregate(m=models.Max("order"))["m"] or 0
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog, order=last + 1)
    return item


def _case_from(task: PlannerTask, user) -> CVECase:
    """A planned-task case with what the card knows."""
    return CVECase.objects.create(
        kind=CVECase.Kind.TASK, title=task.title[:200], assessment=task.description,
        due_date=task.due_date, created_by=user,
        state=CVECase.State.PATCHING if task.is_in_progress else CVECase.State.IDENTIFIED,
    )


@board_access
def link(request: HttpRequest, task_id: str) -> HttpResponse:
    """GET: the "Knyt til Chronicle" form. POST: make or pick the priority /
    case, link it here, and queue the label and back-link in Planner.

    ``action`` = ``priority`` (new prioriteret opgave), ``case`` (new
    planlagt opgave) or ``existing`` with ``target`` = ``p<id>`` / ``c<id>``.
    """
    task = _task(task_id)
    if request.method == "GET":
        return render(request, "planner/partials/link_form.html", {"task": task, **_link_targets()})
    if request.method != "POST" or not can_write(request.user):
        raise PermissionDenied
    action, target = request.POST.get("action"), request.POST.get("target", "")
    with transaction.atomic():
        if action == "priority":
            item, case = _priority_from(task, request.user), None
        elif action == "case":
            item, case = None, _case_from(task, request.user)
        elif action == "existing" and target[:1] == "p" and target[1:].isdigit():
            item, case = get_object_or_404(PriorityItem.objects.active(), pk=int(target[1:])), None
        elif action == "existing" and target[:1] == "c" and target[1:].isdigit():
            item, case = None, get_object_or_404(CVECase, pk=int(target[1:]))
        else:
            return HttpResponse("Vælg en opgave eller sag.", status=400)
        link_obj, created = PlannerLink.objects.get_or_create(
            task_id=task.id, priority_item=item, case=case,
            defaults={"task_title": task.title[:500], "created_by": request.user})
        if created:
            label = settings.PLANNER_LABEL_PRIORITY if item else settings.PLANNER_LABEL_CASE
            _queue(request, PlannerChange.Kind.LINK, task.id,
                   url=request.build_absolute_uri(link_obj.target_url),
                   alias=f"Chronicle: {link_obj.target_label}", label=label)
    return _render_card(request, task)


@board_access
def change(request: HttpRequest, pk: int) -> HttpResponse:
    """What a polling card asks: its change done yet? Returns the card (or,
    for a new card, the placeholder) in its current state."""
    obj = get_object_or_404(PlannerChange, pk=pk)
    task = PlannerTask.objects.select_related("plan").filter(id=obj.task_id).first() if obj.task_id else None
    if task is None:
        return render(request, "planner/partials/new_card.html", {"change": obj})
    failed = obj if obj.status == PlannerChange.Status.FAILED else None
    return _render_card(request, task, failed=failed)
