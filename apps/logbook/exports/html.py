"""
HTML export functionality for week logs.

Generates a standalone HTML document with embedded styles.
"""

from django.conf import settings
from django.template.loader import render_to_string

from apps.oncall.models import OnCallDuty

from ..models import WeekLog


def generate_html(weeklog: WeekLog) -> str:
    """
    Generate a standalone HTML document for a week log.

    Args:
        weeklog: The WeekLog instance to export.

    Returns:
        HTML formatted string with embedded styles.
    """
    # Render HTML template
    context = {
        "weeklog": weeklog,
        "priority_items": weeklog.priority_items.all(),
        "absences": weeklog.absences.all(),
        "incidents": weeklog.incidents.all(),
        "oncall": OnCallDuty.get_for_week(weeklog.year, weeklog.week_number),
    }

    html_content = render_to_string("logbook/exports/weekly_report.html", context)

    # Load CSS for embedding
    css_path = settings.BASE_DIR / "static" / "css" / "pdf_styles.css"
    css_content = ""
    if css_path.exists():
        css_content = css_path.read_text()

    # Inject CSS into head
    style_tag = f"<style>\n{css_content}\n</style>"
    html_content = html_content.replace("</head>", f"{style_tag}\n</head>")

    return html_content
