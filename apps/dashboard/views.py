"""
Views for the dashboard application.

Provides the main dashboard view, HTMX partials for
dynamic content loading, and documentation pages.
"""

import json
import re
from datetime import timedelta
from pathlib import Path

import markdown
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView

from apps.accounts.permissions import editor_required
from apps.logbook.models import HelpdeskTicket, Incident, WeekLog
from apps.oncall.models import OnCallDuty, OnCallSegment, current_watch

from .overview import (
    age_groups,
    changelog_strip,
    donut_segments,
    headline_delta,
    open_ticket_lists,
    sync_state,
)


# Documentation configuration
DOCS_DIR = Path(settings.BASE_DIR) / "docs"
LICENSE_FILE = Path(settings.BASE_DIR) / "LICENSE"

CHANGELOG_FILE = Path(settings.BASE_DIR) / "CHANGELOG.md"

DOCS_PAGES = {
    "changelog": {"file": None, "title": "Changelog", "icon": "clock"},  # Special case
    "setup": {"file": "SETUP.md", "title": "Opsætning", "icon": "wrench"},
    "development": {"file": "DEVELOPMENT.md", "title": "Udvikling", "icon": "code"},
    "deployment": {"file": "DEPLOYMENT.md", "title": "Deployment", "icon": "server"},
    "tasks": {"file": "TASKS.md", "title": "Opgaver", "icon": "clipboard-list"},
    "user-guide": {"file": "USER_GUIDE.md", "title": "Brugervejledning", "icon": "book-open"},
    "sso": {"file": "SSO_SETUP.md", "title": "SSO Opsætning", "icon": "key"},
    "graph-email": {"file": "GRAPH_EMAIL_SETUP.md", "title": "Email Opsætning", "icon": "envelope"},
    "license": {"file": None, "title": "Licens", "icon": "scale"},  # Special case
}


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard view.

    Displays an overview with:
    - Current week status card
    - Helpdesk statistics chart
    - Recent incidents
    - Quick actions
    """

    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs) -> dict:
        """The header sentence and meta line; the cards load as partials."""
        context = super().get_context_data(**kwargs)
        weeklog = WeekLog.get_current_week()
        now = timezone.localtime()
        context["current_week"] = weeklog
        context["iso_week"] = now.isocalendar().week

        # Headline: open tickets from the week's ServiceDesk snapshot (the
        # same number as the KPI card), else the live mirror — also when the
        # week log exists but has not been synced yet (all zeros).
        if weeklog and weeklog.helpdesk_open:
            context["open_count"] = weeklog.helpdesk_open
            context["open_delta"] = headline_delta(weeklog.helpdesk_delta)
        else:
            context["open_count"] = HelpdeskTicket.objects.filter(is_open=True).count()
            context["open_delta"] = None
        context["open_now_mirror"] = HelpdeskTicket.objects.filter(is_open=True).count()

        incidents = weeklog.incidents.all() if weeklog else Incident.objects.none()
        context["incident_count_week"] = incidents.count()
        context["incident_critical_week"] = incidents.filter(
            severity=Incident.Severity.CRITICAL
        ).count()
        if weeklog:
            context["weeklog_task_count"] = weeklog.priority_appearances.filter(
                priority_item__deleted_at__isnull=True
            ).count()
        context["sync"] = sync_state()
        interval = getattr(settings, "SERVICEDESK_SYNC_INTERVAL", 300)
        context["sync_minutes"] = str(max(1, round(interval / 60)))
        context["latest_change"] = _read_latest_changelog_entry()
        return context


class StatisticsView(LoginRequiredMixin, TemplateView):
    """
    Helpdesk and Chronicle statistics on a single page.

    Covers the last 365 days unless ``?fra=``/``?til=`` choose another
    period (see ``statistics.period_from_params``). The numbers are
    computed in ``statistics.py``; the chart series are handed to the
    template's script through ``json_script``.
    """

    template_name = "dashboard/statistics.html"

    def get_context_data(self, **kwargs) -> dict:
        """Add the helpdesk and Chronicle statistics to the context."""
        from .statistics import (
            chronicle_statistics,
            helpdesk_statistics,
            period_from_params,
        )

        context = super().get_context_data(**kwargs)
        now = timezone.now()
        period, period_error = period_from_params(self.request.GET, now)
        helpdesk = helpdesk_statistics(period=period)
        chronicle = chronicle_statistics(period=period)
        context.update(
            helpdesk=helpdesk,
            chronicle=chronicle,
            period=period,
            period_error=period_error,
            today=timezone.localdate(now),
            chart_data={
                "weekdays": helpdesk["weekday_avg"],
                "weekly": helpdesk["weekly"],
                "resolution": helpdesk["resolution"]["buckets"],
                "categories": helpdesk["categories"],
                "technicians": helpdesk["technicians"],
                "priorities": chronicle["priorities"],
                "incidents": chronicle["incidents"],
            },
        )
        return context


# Export formats of the statistics page: (content type, file extension).
STATISTICS_EXPORT_FORMATS = {
    "pdf": ("application/pdf", "pdf"),
    "html": ("text/html; charset=utf-8", "html"),
    "markdown": ("text/markdown; charset=utf-8", "md"),
    "json": ("application/json; charset=utf-8", "json"),
}


@login_required
@editor_required
def statistics_export(request, fmt: str) -> HttpResponse:
    """Download the statistics page as PDF, HTML, Markdown or JSON.

    Editors only, like the week report exports. ``?inline=1`` shows the
    file in the browser instead of downloading it (handy for the JSON).
    ``?fra=``/``?til=`` choose the period, as on the page.
    """
    from . import exports
    from .statistics import period_from_params

    if fmt not in STATISTICS_EXPORT_FORMATS:
        raise Http404("Ukendt format")
    content_type, extension = STATISTICS_EXPORT_FORMATS[fmt]

    now = timezone.now()
    period, _error = period_from_params(request.GET, now)
    data = exports.collect(now, period)
    if fmt == "pdf":
        body = exports.generate_pdf(data)
    elif fmt == "html":
        body = exports.generate_html(data)
    elif fmt == "markdown":
        body = exports.generate_markdown(data)
    else:
        body = json.dumps(
            exports.generate_json(data), ensure_ascii=False, indent=2, cls=DjangoJSONEncoder
        )

    response = HttpResponse(body, content_type=content_type)
    disposition = "inline" if request.GET.get("inline") else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{exports.filename(data, extension)}"'
    return response


def _shared_response(response: HttpResponse) -> HttpResponse:
    """Headers for anything served on a share link: never cached, never indexed."""
    response["Cache-Control"] = "no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    return response


def statistics_shared_json(request, token: str) -> HttpResponse:
    """The statistics JSON on a share link — no login, the token is the key.

    An unknown, expired or revoked token gets the same 404, so the
    response never tells which tokens exist.
    """
    from . import exports
    from .models import StatisticsShareLink

    link = StatisticsShareLink.active(token)
    if link is None:
        raise Http404
    link.record_use()
    body = json.dumps(
        exports.generate_json(exports.collect()), ensure_ascii=False, indent=2, cls=DjangoJSONEncoder
    )
    return _shared_response(HttpResponse(body, content_type="application/json; charset=utf-8"))


def statistics_shared_guide(request, token: str) -> HttpResponse:
    """The guide to the shared JSON, as Markdown, for Claude to read first."""
    from .models import StatisticsShareLink

    link = StatisticsShareLink.active(token)
    if link is None:
        raise Http404
    text = render_to_string(
        "dashboard/statistics_share_guide.md",
        {"link": link, "data_url": request.build_absolute_uri(link.get_data_path())},
    )
    return _shared_response(HttpResponse(text, content_type="text/markdown; charset=utf-8"))


def share_prompt(guide_url: str, data_url: str) -> str:
    """The Danish prompt an editor pastes into Claude together with a link."""
    return (
        "Lav en animeret præsentation af FynBus IT's helpdesk-statistik for de "
        "seneste 12 måneder.\n\n"
        f"1. Læs først vejledningen: {guide_url}\n"
        f"2. Hent derefter data (JSON): {data_url}\n\n"
        "Følg vejledningens forslag til forløb og dens regler for, hvordan tallene "
        "læses. Brug kun tal fra data, skriv al tekst på dansk, og gentag ikke "
        "linkene i præsentationen."
    )


@login_required
@editor_required
def statistics_share(request) -> HttpResponse:
    """List, create and revoke share links for the statistics (editors only)."""
    from .models import StatisticsShareLink

    created = None
    if request.method == "POST":
        if "revoke" in request.POST:
            link = get_object_or_404(StatisticsShareLink, pk=request.POST.get("revoke"))
            link.revoke()
            messages.success(request, f"Linket \u201d{link.label}\u201d er tilbagekaldt og virker ikke længere.")
            return redirect("dashboard:statistics-share")

        label = (request.POST.get("label") or "").strip()[:100] or "Claude Motion"
        valid_days = dict(StatisticsShareLink.VALIDITY_CHOICES)
        try:
            days = int(request.POST.get("days", StatisticsShareLink.DEFAULT_VALIDITY_DAYS))
        except ValueError:
            days = StatisticsShareLink.DEFAULT_VALIDITY_DAYS
        if days not in valid_days:
            days = StatisticsShareLink.DEFAULT_VALIDITY_DAYS
        created = StatisticsShareLink.objects.create(
            label=label,
            created_by=request.user,
            expires_at=timezone.now() + timedelta(days=days),
        )

    links = []
    for link in StatisticsShareLink.objects.select_related("created_by"):
        guide_url = request.build_absolute_uri(link.get_guide_path())
        data_url = request.build_absolute_uri(link.get_data_path())
        links.append({
            "link": link,
            "guide_url": guide_url,
            "data_url": data_url,
            "prompt": share_prompt(guide_url, data_url),
        })
    return render(
        request,
        "dashboard/statistics_share.html",
        {
            "links": links,
            "created_id": created.pk if created else None,
            "validity_choices": StatisticsShareLink.VALIDITY_CHOICES,
            "default_days": StatisticsShareLink.DEFAULT_VALIDITY_DAYS,
        },
    )


def _read_latest_changelog_entry() -> dict | None:
    """Parse CHANGELOG.md and return the most recent entry as {title, body_html}.

    Splits on ``^## `` headers; the first such block becomes the entry. Returns
    None if the file is missing or contains no entries.
    """
    if not CHANGELOG_FILE.exists():
        return None
    raw = CHANGELOG_FILE.read_text(encoding="utf-8")
    sections = re.split(r"^## ", raw, flags=re.MULTILINE)
    if len(sections) < 2:
        return None
    body = sections[1]
    title, _, rest = body.partition("\n")
    md = markdown.Markdown(extensions=["fenced_code"])
    return {
        "title": title.strip(),
        "body_html": mark_safe(md.convert(rest.strip())),
        "strip": changelog_strip(title, rest),
    }


class CurrentWeekPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for current week status card."""

    template_name = "dashboard/partials/current_week.html"

    def get_context_data(self, **kwargs) -> dict:
        """Get current week data."""
        context = super().get_context_data(**kwargs)
        weeklog = WeekLog.get_current_week()

        if weeklog:
            # Auto-close stale items (>6 weeks since last_active_at) before
            # we read the appearance list — keeps the dashboard tidy.
            weeklog.auto_close_stale_priorities()
            context["weeklog"] = weeklog
            # Every appearance for the week (13 is a typical week), done
            # ones included; the card fades those rather than striking them.
            appearances = list(
                weeklog.priority_appearances.select_related("priority_item")
                .filter(priority_item__deleted_at__isnull=True)
                .order_by("order", "id")
            )
            done = sum(1 for a in appearances if a.priority_item.status == "completed")
            context["priority_appearances"] = appearances
            context["task_total"] = len(appearances)
            context["task_done"] = done
            context["task_open"] = len(appearances) - done
            context["absences"] = weeklog.absences.all()[:5]
        else:
            now = timezone.now()
            iso_cal = now.isocalendar()
            context["current_year"] = iso_cal.year
            context["current_week"] = iso_cal.week

        return context


class HelpdeskStatsPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for helpdesk stats cards (polls for live updates).

    When the ServiceDesk sync has stopped (``sync.stale``) the cards are
    dimmed and marked "forældet".
    """

    template_name = "dashboard/partials/helpdesk_stats.html"

    def get_context_data(self, **kwargs) -> dict:
        """Get current week helpdesk stats."""
        context = super().get_context_data(**kwargs)
        context["weeklog"] = WeekLog.get_current_week()
        context["sync"] = sync_state()
        return context


class HelpdeskChartPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for helpdesk statistics chart."""

    template_name = "dashboard/partials/helpdesk_chart.html"


class HelpdeskFlowChartPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for helpdesk new vs closed grouped bar chart."""

    template_name = "dashboard/partials/helpdesk_flow_chart.html"


class OpenBreakdownPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial: the "Åbne sager" bento — open tickets by technician,
    by category (SVG donut) and by age.

    Technicians and categories come from the live ServiceDesk mirror
    (``HelpdeskTicket.open_by_*``, the same helpers as the week report);
    the age groups from the current week's ServiceDesk snapshot.
    """

    template_name = "dashboard/partials/open_breakdown.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        technicians = HelpdeskTicket.open_by_technician()
        categories = HelpdeskTicket.open_by_category()
        top = max((t["count"] for t in technicians["technicians"]), default=0)
        context["technicians"] = [
            {**t, "bar": round(100 * t["count"] / top, 1) if top else 0,
             "muted": t["label"] == HelpdeskTicket.NO_TECHNICIAN_LABEL}
            for t in technicians["technicians"]
        ]
        context["open_total"] = technicians["total"]
        context["category_total"] = categories["total"]
        context["donut"] = donut_segments(categories["categories"])
        context["uncategorised"] = categories.get("uncategorised", 0)
        context["ages"] = age_groups(WeekLog.get_current_week())
        return context


class OpenTicketListsPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial: the six newest and six oldest open helpdesk tickets,
    each linking straight to the request in ServiceDesk."""

    template_name = "dashboard/partials/open_ticket_lists.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context.update(open_ticket_lists())
        return context


class IncidentsPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for recent incidents list."""

    template_name = "dashboard/partials/incidents_list.html"

    # Incidents newer than this are shown; older ones sit behind "Vis ældre".
    RECENT_DAYS = 30
    # How many older incidents the expanded list adds.
    OLDER_LIMIT = 20

    def get_context_data(self, **kwargs) -> dict:
        """Incidents from the last RECENT_DAYS days, plus any still
        unresolved however old, and a capped list of older resolved ones
        that the card reveals on request."""
        context = super().get_context_data(**kwargs)
        cutoff = timezone.now() - timedelta(days=self.RECENT_DAYS)
        incidents = Incident.objects.select_related("weeklog").order_by("-occurred_at")
        older = incidents.filter(occurred_at__lt=cutoff, resolved=True)

        context["incidents"] = incidents.filter(Q(occurred_at__gte=cutoff) | Q(resolved=False))
        context["older_incidents"] = older[: self.OLDER_LIMIT]
        context["older_count"] = older.count()
        context["recent_days"] = self.RECENT_DAYS
        context["unresolved_count"] = Incident.objects.filter(resolved=False).count()
        weeklog = WeekLog.get_current_week()
        week = weeklog.incidents.all() if weeklog else Incident.objects.none()
        context["week_count"] = week.count()
        context["week_critical"] = week.filter(severity=Incident.Severity.CRITICAL).count()
        return context


class OnCallPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for on-call status on the dashboard."""

    template_name = "dashboard/partials/oncall_status.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        oncall = OnCallDuty.get_current()
        context["oncall"] = oncall
        # Split weeks (mid-week handover, FR #5) get an extra coverage line.
        segments = (
            list(OnCallSegment.for_week(oncall.year, oncall.week_number)) if oncall else []
        )
        context["oncall_segments"] = segments if len(segments) > 1 else []
        context["watch"] = current_watch()
        return context


class OnCallMiniPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial: the sidebar's small "Rådighedsvagt nu" card."""

    template_name = "components/partials/oncall_mini.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["watch"] = current_watch()
        return context


class FooterVersionPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for footer version display."""

    template_name = "components/partials/footer_version.html"


class LatestChangePartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for the dashboard's "Seneste ændring" card.

    Reads the top entry from CHANGELOG.md and re-emits it. Polled every
    300s so newly-deployed changes show up without a page reload.
    """

    template_name = "dashboard/partials/latest_change.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["latest_change"] = _read_latest_changelog_entry()
        return context


@login_required
def sync_servicedesk_stats(request):
    """HTMX endpoint: run a ServiceDesk sync now and return the KPI cards.

    Runs both halves of the scheduled sync — the weeklog counters *and*
    an incremental ticket-mirror update. The "synk fejlede"/"forældet"
    state (``sync_state``) is read from the mirror, so refreshing only
    the counters left the dashboard looking stale after a manual sync.

    The cards are returned with an error pill when the sync fails. With
    ``reload=1`` (the headline's "Prøv igen" button) a successful sync
    answers ``HX-Refresh`` so the whole page picks up the fresh state.
    """
    import logging

    from apps.logbook.services import ticket_mirror
    from apps.logbook.services.servicedesk import ServiceDeskClient

    logger = logging.getLogger(__name__)

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    client = ServiceDeskClient()
    sync_error = None
    if not client.enabled:
        logger.warning("ServiceDesk sync triggered but disabled")
        sync_error = "ServiceDesk sync er deaktiveret"
    else:
        try:
            weeklog = WeekLog.get_or_create_current_week()
            stats = client.get_week_stats(weeklog.year, weeklog.week_number)
            weeklog.apply_helpdesk_stats(stats)
            logger.info("Manual sync: %s new=%d closed=%d open=%d by_age=%s",
                        weeklog.week_label, stats["created"], stats["closed"], stats["open"],
                        stats.get("open_by_age") or "n/a")
            if ticket_mirror.sync_incremental(client) is None:
                sync_error = "Synk med ServiceDesk fejlede"
        except Exception:
            logger.exception("Manual ServiceDesk sync failed")
            sync_error = "Synk med ServiceDesk fejlede"

    html = render_to_string(
        "dashboard/partials/helpdesk_stats.html",
        {"weeklog": WeekLog.get_current_week(), "sync": sync_state(), "sync_error": sync_error},
        request=request,
    )
    response = HttpResponse(html)
    if sync_error is None and request.POST.get("reload"):
        response["HX-Refresh"] = "true"
    return response


@login_required
def helpdesk_chart_data(request) -> JsonResponse:
    """
    API endpoint for helpdesk chart data.

    Returns JSON data for the last 52 weeks of helpdesk statistics.
    """
    # Get current week info
    now = timezone.now()
    iso_cal = now.isocalendar()

    # Fetch last 52 weeks of data
    weeks_data = []
    weeklogs = WeekLog.objects.order_by("-year", "-week_number")[:52]

    # Build data for chart (reverse to show oldest first)
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

    # Calculate statistics
    if weeks_data:
        total_new = sum(w["new"] for w in weeks_data)
        total_closed = sum(w["closed"] for w in weeks_data)
        avg_new = total_new / len(weeks_data)
        avg_closed = total_closed / len(weeks_data)
    else:
        avg_new = avg_closed = 0

    return JsonResponse(
        {
            "weeks": weeks_data,
            "stats": {
                "avg_new": round(avg_new, 1),
                "avg_closed": round(avg_closed, 1),
                "current_open": weeks_data[-1]["open"] if weeks_data else 0,
            },
        }
    )


class TaskTimelinePartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial view for task timeline chart."""

    template_name = "dashboard/partials/task_timeline_chart.html"


@login_required
def task_timeline_chart_data(request) -> JsonResponse:
    """
    JSON API endpoint for task timeline chart data.

    Returns active tasks plus recently completed tasks (within 7 days)
    with planned dates, status, assignees, and approvers for Gantt chart.
    """
    import logging
    from datetime import timedelta

    from django.db.models import Q
    from django.utils import timezone

    from apps.tasks.models import Task

    logger = logging.getLogger(__name__)

    try:
        one_week_ago = timezone.now() - timedelta(days=7)
        tasks = (
            Task.objects.filter(
                Q(~Q(status=Task.Status.COMPLETE))
                | Q(
                    status=Task.Status.COMPLETE,
                    state_changes__to_state="complete",
                    state_changes__changed_at__gte=one_week_ago,
                )
            )
            .distinct()
            .select_related("created_by")
            .prefetch_related("state_changes", "assigned_to")
            .order_by("planned_start", "created_at")
        )

        data = []
        for task in tasks:
            data.append(
                {
                    "id": task.pk,
                    "title": task.title,
                    "planned_start": (
                        task.planned_start.isoformat() if task.planned_start else None
                    ),
                    "planned_end": (
                        task.planned_end.isoformat() if task.planned_end else None
                    ),
                    "status": task.status,
                    "state_changes": [
                        {
                            "changed_at": sc.changed_at.isoformat(),
                            "from_state": sc.from_state,
                            "to_state": sc.to_state,
                        }
                        for sc in task.state_changes.all()
                    ],
                    "approvers": [
                        name.strip()
                        for name in task.approvers.split(",")
                        if name.strip()
                    ] if task.approvers else [],
                    "assignees": [
                        u.get_full_name() or u.username
                        for u in task.assigned_to.all()
                    ],
                }
            )

        return JsonResponse({"tasks": data})
    except Exception:
        logger.exception("Error in task_timeline_chart_data")
        return JsonResponse({"error": "Internal server error"}, status=500)


class DocsIndexView(LoginRequiredMixin, TemplateView):
    """Documentation index page listing all available docs."""

    template_name = "dashboard/docs/index.html"

    def get_context_data(self, **kwargs) -> dict:
        """Add docs list to context."""
        context = super().get_context_data(**kwargs)
        context["docs_pages"] = DOCS_PAGES
        return context


class DocsPageView(LoginRequiredMixin, TemplateView):
    """Render a documentation page from Markdown."""

    template_name = "dashboard/docs/page.html"

    def get_context_data(self, **kwargs) -> dict:
        """Load and render the markdown file."""
        context = super().get_context_data(**kwargs)
        slug = self.kwargs.get("slug")

        if slug not in DOCS_PAGES:
            raise Http404("Documentation page not found")

        page_info = DOCS_PAGES[slug]
        context["page_title"] = page_info["title"]
        context["docs_pages"] = DOCS_PAGES
        context["current_slug"] = slug

        # Handle special-case files
        if slug == "changelog":
            if CHANGELOG_FILE.exists():
                md_content = CHANGELOG_FILE.read_text(encoding="utf-8")
                md = markdown.Markdown(
                    extensions=["fenced_code", "tables", "toc", "sane_lists"]
                )
                context["content"] = md.convert(md_content)
                context["toc"] = md.toc
            else:
                context["content"] = "<p>Changelog not found.</p>"
        elif slug == "license":
            if LICENSE_FILE.exists():
                content = LICENSE_FILE.read_text(encoding="utf-8")
                context["content"] = f"<pre class='license-text'>{content}</pre>"
            else:
                context["content"] = "<p>License file not found.</p>"
        else:
            # Regular markdown file
            file_path = DOCS_DIR / page_info["file"]
            if not file_path.exists():
                raise Http404(f"Documentation file not found: {page_info['file']}")

            md_content = file_path.read_text(encoding="utf-8")

            # Configure markdown with extensions
            md = markdown.Markdown(
                extensions=[
                    "fenced_code",
                    "tables",
                    "toc",
                    "nl2br",
                    "sane_lists",
                ]
            )
            context["content"] = md.convert(md_content)
            context["toc"] = md.toc

        return context
