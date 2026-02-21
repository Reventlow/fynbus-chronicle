"""
PDF export functionality for week logs.

Uses WeasyPrint to generate PDF documents from HTML templates.
"""

from django.template.loader import render_to_string

from apps.oncall.models import OnCallDuty

from ..models import WeekLog
from .chart import generate_helpdesk_chart


def generate_pdf(weeklog: WeekLog) -> bytes:
    """
    Generate a PDF document for a week log.

    Args:
        weeklog: The WeekLog instance to export.

    Returns:
        PDF content as bytes.
    """
    try:
        from weasyprint import CSS, HTML
    except ImportError as e:
        raise ImportError(
            "WeasyPrint is required for PDF generation. "
            "Install it with: pip install WeasyPrint"
        ) from e

    # Generate helpdesk trend chart
    chart_image = generate_helpdesk_chart(weeklog)

    # Render HTML template
    context = {
        "weeklog": weeklog,
        "priority_items": weeklog.priority_items.all(),
        "absences": weeklog.absences.all(),
        "incidents": weeklog.incidents.all(),
        "oncall": OnCallDuty.get_for_week(weeklog.year, weeklog.week_number),
        "chart_image": chart_image,
    }

    html_content = render_to_string("logbook/exports/weekly_report.html", context)

    # Generate PDF with custom CSS
    from django.conf import settings

    css_path = settings.BASE_DIR / "static" / "css" / "pdf_styles.css"

    html = HTML(string=html_content)
    css = CSS(filename=str(css_path)) if css_path.exists() else None

    if css:
        pdf_bytes = html.write_pdf(stylesheets=[css])
    else:
        pdf_bytes = html.write_pdf()

    return pdf_bytes
