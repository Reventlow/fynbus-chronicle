"""
Email export functionality for week logs.

Sends weekly reports via email in HTML, PDF, or both formats.
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from apps.oncall.models import OnCallDuty

from ..models import WeekLog
from .chart import generate_helpdesk_chart, generate_helpdesk_flow_chart
from .pdf import generate_pdf


def send_weeklog_email(
    weeklog: WeekLog, format: str = "both", from_email: str | None = None
) -> tuple[bool, str]:
    """
    Send a week log report via email.

    Args:
        weeklog: The WeekLog instance to send.
        format: Email format - "html", "pdf", or "both".
        from_email: Sender address. Falls back to DEFAULT_FROM_EMAIL.

    Returns:
        Tuple of (success: bool, message: str).
    """
    if format not in ("html", "pdf", "both"):
        return False, f"Ugyldigt format: {format}. Brug 'html', 'pdf' eller 'both'."

    recipients = getattr(settings, "CHRONICLE_EMAIL_RECIPIENTS", [])

    if not recipients:
        return False, "Ingen email-modtagere konfigureret. Tjek CHRONICLE_EMAIL_RECIPIENTS."

    # Generate helpdesk charts
    chart_image = generate_helpdesk_chart(weeklog)
    flow_chart_image = generate_helpdesk_flow_chart(weeklog)

    # Calculate weekly averages
    avgs = weeklog.helpdesk_weekly_averages()

    # Render HTML body
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

    try:
        body_html = render_to_string("logbook/exports/email_body.html", context)
    except Exception as e:
        return False, f"Fejl ved generering af email-indhold: {e}"

    # Create email
    subject = f"FynBus IT Ugelog - {weeklog.week_label}"
    if not from_email:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "it@fynbus.dk")

    if format == "pdf":
        # Plain text body with PDF attachment only
        body = f"FynBus IT Ugelog - {weeklog.week_label}\n\nRapporten er vedhæftet som PDF."
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=recipients,
        )
    else:
        # HTML body for "html" and "both"
        email = EmailMessage(
            subject=subject,
            body=body_html,
            from_email=from_email,
            to=recipients,
        )
        email.content_subtype = "html"

    # Attach PDF for "pdf" and "both"
    if format in ("pdf", "both"):
        try:
            pdf_content = generate_pdf(weeklog)
        except Exception as e:
            return False, f"Fejl ved generering af PDF: {e}"

        filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.pdf"
        email.attach(filename, pdf_content, "application/pdf")

    # Send email
    try:
        email.send(fail_silently=False)
        format_label = {"html": "HTML", "pdf": "PDF", "both": "HTML + PDF"}[format]
        return True, f"Email ({format_label}) sendt til {len(recipients)} modtager(e)."
    except Exception as e:
        return False, f"Fejl ved afsendelse af email: {e}"
