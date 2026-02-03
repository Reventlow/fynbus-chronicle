"""
Views for the dashboard application.

Provides the main dashboard view, HTMX partials for
dynamic content loading, and documentation pages.
"""

from pathlib import Path

import markdown
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView

from apps.logbook.models import Incident, WeekLog


# Documentation configuration
DOCS_DIR = Path(settings.BASE_DIR) / "docs"
LICENSE_FILE = Path(settings.BASE_DIR) / "LICENSE"

DOCS_PAGES = {
    "setup": {"file": "SETUP.md", "title": "Opsætning", "icon": "wrench"},
    "development": {"file": "DEVELOPMENT.md", "title": "Udvikling", "icon": "code"},
    "deployment": {"file": "DEPLOYMENT.md", "title": "Deployment", "icon": "server"},
    "user-guide": {"file": "USER_GUIDE.md", "title": "Brugervejledning", "icon": "book-open"},
    "sso": {"file": "SSO_SETUP.md", "title": "SSO Opsætning", "icon": "key"},
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
        """Add dashboard data to context."""
        context = super().get_context_data(**kwargs)
        context["current_week"] = WeekLog.get_current_week()
        return context


class CurrentWeekPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for current week status card."""

    template_name = "dashboard/partials/current_week.html"

    def get_context_data(self, **kwargs) -> dict:
        """Get current week data."""
        context = super().get_context_data(**kwargs)
        weeklog = WeekLog.get_current_week()

        if weeklog:
            context["weeklog"] = weeklog
            context["priority_items"] = weeklog.priority_items.filter(
                status__in=["ongoing", "blocked"]
            )[:5]
            context["absences"] = weeklog.absences.all()[:5]
        else:
            now = timezone.now()
            iso_cal = now.isocalendar()
            context["current_year"] = iso_cal.year
            context["current_week"] = iso_cal.week

        return context


class HelpdeskStatsPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for helpdesk stats cards (polls for live updates)."""

    template_name = "dashboard/partials/helpdesk_stats.html"

    def get_context_data(self, **kwargs) -> dict:
        """Get current week helpdesk stats."""
        context = super().get_context_data(**kwargs)
        context["weeklog"] = WeekLog.get_current_week()
        return context


class HelpdeskChartPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for helpdesk statistics chart."""

    template_name = "dashboard/partials/helpdesk_chart.html"


class IncidentsPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial for recent incidents list."""

    template_name = "dashboard/partials/incidents_list.html"

    def get_context_data(self, **kwargs) -> dict:
        """Get recent incidents."""
        context = super().get_context_data(**kwargs)

        # Get incidents from last 4 weeks
        context["incidents"] = Incident.objects.select_related("weeklog").order_by(
            "-occurred_at"
        )[:10]

        # Get unresolved count
        context["unresolved_count"] = Incident.objects.filter(resolved=False).count()

        return context


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

        # Handle license file specially
        if slug == "license":
            if LICENSE_FILE.exists():
                content = LICENSE_FILE.read_text(encoding="utf-8")
                # Wrap in code block for license
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
