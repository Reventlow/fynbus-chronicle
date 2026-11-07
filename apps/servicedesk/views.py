"""The ServiceDesk page and ticket links.

The page reads the local ticket mirror (``HelpdeskTicket``, kept in step
by the sync container), so it costs no ServiceDesk call to show. Tickets
are split into three groups:

* **Mine**: assigned to the logged-in user (the technician's e-mail in
  ServiceDesk, or failing that their name, matches the Chronicle user);
* **Ikke tildelt**: no technician;
* **Alle andres**: assigned to someone else.

"Uløste" shows the tickets open now, oldest first; "Lukkede" the tickets
closed within the last 7, 30 or 90 days, newest first. "Synk nu" runs the
same sync as the dashboard's button (this week's counts plus the changed
tickets) and reloads the page.

Editors can link a ticket to a prioriteret opgave or a sag (an existing
one, or a new one made from the ticket). Linking puts a ServiceDesk pill
on the priority or case, and adds an internal note to the ticket in
ServiceDesk with a link back to Chronicle. **This is the one place the
web container writes to ServiceDesk**; the note is made straight away,
with the API key's technician as its author and the editor's name in the
text.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from apps.accounts.permissions import is_editor
from apps.cves.models import CVECase
from apps.dashboard.overview import sync_state
from apps.logbook.models import (
    HelpdeskTicket,
    PriorityItem,
    PriorityItemAppearance,
    WeekLog,
)
from apps.logbook.services.servicedesk import ServiceDeskClient

from .models import TicketLink

OPEN, CLOSED = "open", "closed"
CLOSED_DAYS = (7, 30, 90)
DEFAULT_CLOSED_DAYS = 30

GROUPS = (
    ("mine", "Mine sager", "Tildelt dig i ServiceDesk."),
    ("unassigned", "Ikke tildelt", "Ingen tekniker endnu."),
    ("others", "Alle andres", "Tildelt en anden tekniker."),
)


# --- who is "me" ----------------------------------------------------------------------


def _me(user) -> tuple[str, str]:
    """The user's e-mail and full name, lower-cased, to match a technician."""
    return (user.email or "").strip().lower(), (user.get_full_name() or "").strip().casefold()


def is_mine(ticket: HelpdeskTicket, me: tuple[str, str]) -> bool:
    """True if the ticket's technician is this user.

    E-mail first (the mirror keeps the technician's e-mail); the name is
    the fallback for tickets mirrored before the e-mail was, and for
    technicians whose ServiceDesk e-mail differs from their login.
    """
    email, name = me
    if not ticket.technician:
        return False
    if email and ticket.technician_email and ticket.technician_email.lower() == email:
        return True
    return bool(name) and ticket.technician.strip().casefold() == name


def split(tickets, user) -> dict[str, list]:
    """Tickets into the three groups, keeping their order."""
    me = _me(user)
    groups: dict[str, list] = {key: [] for key, *_ in GROUPS}
    for ticket in tickets:
        if not ticket.technician:
            groups["unassigned"].append(ticket)
        elif is_mine(ticket, me):
            groups["mine"].append(ticket)
        else:
            groups["others"].append(ticket)
    return groups


# --- age ------------------------------------------------------------------------------


def age_text(delta: timedelta) -> str:
    """Short Danish age: "under 1 t", "5 t", "1 dag", "12 dage"."""
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        return "under 1 t"
    if hours < 24:
        return f"{hours} t"
    days = delta.days
    return f"{days} dag" if days == 1 else f"{days} dage"


def age_color(delta: timedelta) -> str:
    """The week report's liggetid colour for an age."""
    days = delta.days
    for _field, _label, _low, high, color in WeekLog.HELPDESK_AGE_BUCKETS:
        if high is None or days <= high:
            return color
    return WeekLog.HELPDESK_AGE_BUCKETS[-1][-1]


def decorate(tickets, now=None) -> list:
    """Add ``age``/``age_text``/``age_color`` and ``links`` to each ticket.

    Open tickets: time since created. Closed: how long it took to close.
    """
    now = now or timezone.now()
    tickets = list(tickets)
    links = defaultdict(list)
    for link in (TicketLink.objects.filter(sdp_id__in=[t.sdp_id for t in tickets])
                 .select_related("priority_item", "case")):
        links[link.sdp_id].append(link)
    for ticket in tickets:
        end = ticket.closed_at if (ticket.closed_at and not ticket.is_open) else now
        ticket.age = max(end - ticket.created_at, timedelta(0))
        ticket.age_text = age_text(ticket.age)
        ticket.age_color = age_color(ticket.age)
        ticket.links = links.get(ticket.sdp_id, [])
    return tickets


# --- the page -------------------------------------------------------------------------


@login_required
def tickets(request: HttpRequest) -> HttpResponse:
    tab = CLOSED if request.GET.get("vis") == CLOSED else OPEN
    try:
        days = int(request.GET.get("dage", DEFAULT_CLOSED_DAYS))
    except ValueError:
        days = DEFAULT_CLOSED_DAYS
    if days not in CLOSED_DAYS:
        days = DEFAULT_CLOSED_DAYS

    now = timezone.now()
    open_qs = HelpdeskTicket.objects.filter(is_open=True)
    if tab == OPEN:
        rows = open_qs.order_by("created_at")
    else:
        rows = HelpdeskTicket.objects.filter(is_open=False, closed_at__gte=now - timedelta(days=days)) \
                                     .order_by("-closed_at")
    groups = split(decorate(rows, now), request.user)

    return render(request, "servicedesk/tickets.html", {
        "tab": tab,
        "days": days,
        "closed_days": CLOSED_DAYS,
        "groups": [{"key": key, "title": title, "hint": hint, "tickets": groups[key]}
                   for key, title, hint in GROUPS],
        "open_count": open_qs.count(),
        "can_link": is_editor(request.user),
        "servicedesk_url": (settings.SERVICEDESK_URL or "").rstrip("/"),
        "sync": sync_state(now),
        "sync_enabled": settings.SERVICEDESK_SYNC_ENABLED,
        "me_matched": bool(_me(request.user)[0] or _me(request.user)[1]),
    })


@require_POST
@login_required
def sync(request: HttpRequest) -> HttpResponse:
    """"Synk nu": sync with ServiceDesk, then reload the page (HX-Refresh).
    On failure, the reason is returned for the button's message slot."""
    from apps.logbook.tasks import sync_now

    error = sync_now()
    if error:
        return HttpResponse(error)
    response = HttpResponse("")
    response["HX-Refresh"] = "true"
    return response


def _render_row(request: HttpRequest, ticket: HelpdeskTicket) -> HttpResponse:
    (ticket,) = decorate([ticket])
    return render(request, "servicedesk/partials/ticket.html",
                  {"ticket": ticket, "can_link": is_editor(request.user)})


# --- linking --------------------------------------------------------------------------


def _link_targets() -> dict:
    return {
        "priorities": PriorityItem.objects.active().exclude(status=PriorityItem.Status.COMPLETED)
                                          .order_by("title")[:300],
        "cases": CVECase.objects.open().order_by("-updated_at")[:300],
    }


def _title(ticket: HelpdeskTicket) -> str:
    return (ticket.subject or f"ServiceDesk-sag #{ticket.sdp_id}")[:200]


def _priority_from(ticket: HelpdeskTicket, user) -> PriorityItem:
    """A priority item on this week's log, named after the ticket."""
    weeklog = WeekLog.get_or_create_current_week(user)
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog, title=_title(ticket), priority=PriorityItem.Priority.MEDIUM,
        status=PriorityItem.Status.ONGOING if ticket.status == "I gang" else PriorityItem.Status.NOT_STARTED,
        notes=f"Fra ServiceDesk-sag #{ticket.sdp_id}.",
    )
    last = weeklog.priority_appearances.aggregate(m=models.Max("order"))["m"] or 0
    PriorityItemAppearance.objects.create(priority_item=item, weeklog=weeklog, order=last + 1)
    return item


def _case_from(ticket: HelpdeskTicket, user) -> CVECase:
    """A planned-task case named after the ticket."""
    return CVECase.objects.create(
        kind=CVECase.Kind.TASK, title=_title(ticket), created_by=user,
        assessment=f"Fra ServiceDesk-sag #{ticket.sdp_id}.",
        state=CVECase.State.PATCHING if ticket.status == "I gang" else CVECase.State.IDENTIFIED,
    )


def note_html(link: TicketLink, request: HttpRequest, *, removed: bool = False) -> str:
    """The internal note: what the ticket is linked to, by whom, with a link."""
    who = request.user.get_full_name() or request.user.get_username()
    return format_html(
        '<p>{} Chronicle: <a href="{}" target="_blank">{}: {}</a> (af {}).</p>',
        "Ikke længere knyttet til" if removed else "Knyttet til",
        request.build_absolute_uri(link.target_url), link.target_label, link.target_title, who,
    )


def send_note(link: TicketLink, request: HttpRequest, *, removed: bool = False) -> str | None:
    """Add the note in ServiceDesk; on a link, record the outcome on it."""
    error = ServiceDeskClient().add_note(link.sdp_id, note_html(link, request, removed=removed))
    if not removed:
        link.note_error = error or ""
        if error is None:
            link.note_added_at = timezone.now()
        link.save(update_fields=["note_error", "note_added_at"])
    return error


def editor_only(view):
    """Logged in and an editor (not the read-only Viewer group)."""
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_editor(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


@editor_only
def link(request: HttpRequest, sdp_id: int) -> HttpResponse:
    """GET: the "Knyt til Chronicle" form. POST: make or pick the priority /
    case, link the ticket to it and add the note in ServiceDesk.

    ``action`` = ``priority`` (new prioriteret opgave), ``case`` (new
    planlagt opgave) or ``existing`` with ``target`` = ``p<id>`` / ``c<id>``.
    """
    ticket = get_object_or_404(HelpdeskTicket, sdp_id=sdp_id)
    if request.method == "GET":
        return render(request, "servicedesk/partials/link_form.html", {"ticket": ticket, **_link_targets()})
    if request.method != "POST":
        raise PermissionDenied
    action, target = request.POST.get("action"), request.POST.get("target", "")
    with transaction.atomic():
        if action == "priority":
            item, case = _priority_from(ticket, request.user), None
        elif action == "case":
            item, case = None, _case_from(ticket, request.user)
        elif action == "existing" and target[:1] == "p" and target[1:].isdigit():
            item, case = get_object_or_404(PriorityItem.objects.active(), pk=int(target[1:])), None
        elif action == "existing" and target[:1] == "c" and target[1:].isdigit():
            item, case = None, get_object_or_404(CVECase, pk=int(target[1:]))
        else:
            return HttpResponse("Vælg en opgave eller sag.", status=400)
        link_obj, created = TicketLink.objects.get_or_create(
            sdp_id=ticket.sdp_id, priority_item=item, case=case,
            defaults={"subject": ticket.subject[:255], "created_by": request.user})
    if created:
        send_note(link_obj, request)
    return _render_row(request, ticket)


@require_POST
@editor_only
def unlink(request: HttpRequest, pk: int) -> HttpResponse:
    """Remove a link, and say so in a note on the ticket (best effort)."""
    link_obj = get_object_or_404(TicketLink.objects.select_related("priority_item", "case"), pk=pk)
    sdp_id = link_obj.sdp_id
    if link_obj.note_added_at:  # only worth saying if the link was announced
        send_note(link_obj, request, removed=True)
    link_obj.delete()
    ticket = HelpdeskTicket.objects.filter(sdp_id=sdp_id).first()
    if ticket is None:
        response = HttpResponse(status=204)
        response["HX-Refresh"] = "true"
        return response
    return _render_row(request, ticket)


@require_POST
@editor_only
def retry_note(request: HttpRequest, pk: int) -> HttpResponse:
    """Try the note in ServiceDesk again after it failed."""
    link_obj = get_object_or_404(TicketLink.objects.select_related("priority_item", "case"), pk=pk)
    if not link_obj.note_added_at:
        send_note(link_obj, request)
    ticket = get_object_or_404(HelpdeskTicket, sdp_id=link_obj.sdp_id)
    return _render_row(request, ticket)
