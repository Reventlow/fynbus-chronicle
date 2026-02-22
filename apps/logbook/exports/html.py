"""
HTML export functionality for week logs.

Generates a standalone HTML document with embedded styles.
The PDF styles (pdf_styles.css) are injected for shared layout, and
supplementary browser-specific styles are added so the HTML export
renders well in web browsers (the PDF export is unaffected).
"""

from django.conf import settings
from django.template.loader import render_to_string

from apps.oncall.models import OnCallDuty

from ..models import WeekLog
from .chart import generate_helpdesk_chart, generate_helpdesk_flow_chart

# Browser-specific overrides layered on top of pdf_styles.css.
# These handle differences between WeasyPrint (print) and browser rendering:
# - Max-width centering for the document body
# - Padding and margin adjustments using px instead of cm/pt
# - Responsive image constraints
# - Border-radius polish (stripped on Outlook paste but looks nice in browser)
_BROWSER_CSS = """
/* ── Browser-specific overrides for HTML export ── */
body {
  max-width: 800px;
  margin: 0 auto;
  padding: 30px 40px;
  background-color: #FFFFFF;
}

/* Responsive images */
img {
  max-width: 100%;
  height: auto;
}

/*
 * Charts row and stats grid are now real <table> elements in the HTML
 * template (for Outlook paste compatibility).  Only minimal overrides
 * are needed here for browser polish.
 */
.charts-row {
  margin: 8px 0;
}

.chart-col img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 8px;
}

.stat-item {
  border-radius: 12px;
}

/* Section spacing in px for browsers */
.section {
  margin-bottom: 24px;
}

/* Item row spacing */
.item-row {
  margin-bottom: 8px;
  padding: 10px 14px;
}

.item-row-resolution {
  padding: 8px 12px;
  margin-top: 6px;
}

/* Summary box padding */
.summary-box {
  padding: 14px 16px;
  margin: 12px 0;
}

/* Report meta */
.report-meta {
  padding: 14px 16px;
  margin-bottom: 20px;
}

/* Report footer */
.report-footer {
  margin-top: 30px;
  padding-top: 12px;
}
"""


def generate_html(weeklog: WeekLog) -> str:
    """
    Generate a standalone HTML document for a week log.

    Injects both the shared pdf_styles.css and browser-specific overrides
    so the output looks as close to the PDF as possible when viewed in a
    web browser.

    Args:
        weeklog: The WeekLog instance to export.

    Returns:
        HTML formatted string with embedded styles.
    """
    # Generate helpdesk charts
    chart_image = generate_helpdesk_chart(weeklog)
    flow_chart_image = generate_helpdesk_flow_chart(weeklog)

    # Calculate weekly averages
    avgs = weeklog.helpdesk_weekly_averages()

    # Render HTML template
    context = {
        "weeklog": weeklog,
        "priority_items": weeklog.priority_items.all(),
        "absences": weeklog.absences.all(),
        "incidents": weeklog.incidents.all(),
        "oncall": OnCallDuty.get_for_week(weeklog.year, weeklog.week_number),
        "chart_image": chart_image,
        "flow_chart_image": flow_chart_image,
        "avg_new": avgs["avg_new"],
        "avg_closed": avgs["avg_closed"],
    }

    html_content = render_to_string("logbook/exports/weekly_report.html", context)

    # Load shared PDF/print CSS
    css_path = settings.BASE_DIR / "static" / "css" / "pdf_styles.css"
    css_content = ""
    if css_path.exists():
        css_content = css_path.read_text()

    # Inject shared styles + browser overrides into <head>.
    # Order matters: pdf_styles.css first, then browser overrides on top.
    style_tag = (
        f"<style>\n{css_content}\n</style>\n"
        f"<style>\n{_BROWSER_CSS}\n</style>"
    )
    html_content = html_content.replace("</head>", f"{style_tag}\n</head>")

    return html_content
