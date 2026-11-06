"""Planner board views. **Web container: never calls Microsoft Graph.**

The board renders the local mirror. "Synk nu" only records a request for
the sync container. Connecting the service account sends a staff member to
Microsoft (the URL needs the client id, not the secret); Microsoft's code
comes back here and is sealed straight away for the sync container, which
alone can open it and redeem it.

Who may see what:
* the board, its status and "Synk nu": editors (not the read-only Viewer
  group), since the plan is internal IT work;
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
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from apps.accounts.permissions import is_editor

from . import crypto
from .graph import authorize_url
from .models import (
    PendingSignIn,
    PlannerBucket,
    PlannerConnection,
    PlannerPerson,
    PlannerPlan,
    PlannerTask,
    SyncState,
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


@board_access
def board(request: HttpRequest) -> HttpResponse:
    plan = PlannerPlan.objects.filter(id=settings.PLANNER_PLAN_ID).first()
    columns = []
    if plan:
        people = {p.id: p for p in PlannerPerson.objects.all()}
        tasks = list(PlannerTask.objects.filter(plan=plan).select_related("bucket"))
        for task in tasks:
            task.people = [people[i] for i in task.assignee_ids if i in people]
            task.labels = [
                {"name": plan.labels[k], "color": LABEL_COLORS[(int(k[8:]) - 1) % 25]}
                for k in task.label_keys if k in plan.labels
            ]
        by_bucket = {key: list(group) for key, group in
                     groupby(sorted(tasks, key=lambda t: (t.bucket_id or "", t.order_hint)),
                             key=lambda t: t.bucket_id or "")}
        for bucket in PlannerBucket.objects.filter(plan=plan):
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


@staff_only
@require_POST
def connect(request: HttpRequest) -> HttpResponse:
    """Send a staff member to Microsoft to sign in as the service account."""
    if not (settings.PLANNER_CLIENT_ID and crypto.can_seal()):
        messages.error(request, "Planner-forbindelsen er ikke sat op (PLANNER_CLIENT_ID / PLANNER_PUBLIC_KEY).")
        return redirect("planner:board")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect_uri = _redirect_uri(request)
    request.session[SESSION_KEY] = {"state": state, "verifier": verifier, "redirect_uri": redirect_uri}
    return redirect(authorize_url(state=state, code_challenge=challenge, redirect_uri=redirect_uri))


@staff_only
def connect_callback(request: HttpRequest) -> HttpResponse:
    """Microsoft returns here; seal the code for the sync container."""
    flow = request.session.pop(SESSION_KEY, None)
    if not flow or not secrets.compare_digest(request.GET.get("state", ""), flow["state"]):
        messages.error(request, "Login-forsøget kunne ikke genkendes. Start forbindelsen igen.")
        return redirect("planner:board")
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
