"""
PDF export functionality for week logs.

Uses WeasyPrint to generate PDF documents from HTML templates.
"""

from django.template.loader import render_to_string

from apps.images.embedding import embed_as_data_uris
from apps.oncall.models import OnCallDuty, OnCallSegment

from ..models import WeekLog
from .chart import (
    generate_category_donut,
    generate_technician_donut,
    generate_helpdesk_chart,
    generate_helpdesk_flow_chart,
)

# Pasted images are capped to the printable width of an A4 page.
PDF_IMAGE_MAX_WIDTH = 640


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

    # Generate helpdesk charts
    chart_image = generate_helpdesk_chart(weeklog)
    open_categories = weeklog.helpdesk_open_by_category()
    open_technicians = weeklog.helpdesk_open_by_technician()
    flow_chart_image = generate_helpdesk_flow_chart(weeklog)

    # Calculate weekly averages
    avgs = weeklog.helpdesk_weekly_averages()

    # Render HTML template
    context = {
        "weeklog": weeklog,
        "priority_items": weeklog.priority_appearances.select_related("priority_item").all(),
        "absences": weeklog.absences.all(),
        "incidents": weeklog.incidents.all(),
        "oncall": OnCallDuty.get_for_week(weeklog.year, weeklog.week_number),
        "oncall_split": OnCallSegment.split_week_display(weeklog.year, weeklog.week_number),
        "chart_image": chart_image,
        "flow_chart_image": flow_chart_image,
        "open_categories": open_categories,
        "category_chart_image": generate_category_donut(open_categories),
        "open_technicians": open_technicians,
        "technician_chart_image": generate_technician_donut(open_technicians),
        "avg_new": avgs["avg_new"],
        "avg_closed": avgs["avg_closed"],
    }

    html_content = render_to_string("logbook/exports/weekly_report.html", context)
    # Pasted images sit behind a login; carry the bytes in the document.
    html_content = embed_as_data_uris(html_content, max_width=PDF_IMAGE_MAX_WIDTH)

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
