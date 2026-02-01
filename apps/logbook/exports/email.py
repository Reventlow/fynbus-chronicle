"""
Email export functionality for week logs.

Sends weekly reports via email with PDF attachment.
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from ..models import WeekLog
from .pdf import generate_pdf


def send_weeklog_email(weeklog: WeekLog) -> tuple[bool, str]:
    """
    Send a week log report via email.

    Sends an email with the weekly summary in the body and
    a PDF attachment with the full report.

    Args:
        weeklog: The WeekLog instance to send.

    Returns:
        Tuple of (success: bool, message: str).
    """
    recipients = getattr(settings, "CHRONICLE_EMAIL_RECIPIENTS", [])

    if not recipients:
        return False, "Ingen email-modtagere konfigureret. Tjek CHRONICLE_EMAIL_RECIPIENTS."

    # Render email body
    context = {
        "weeklog": weeklog,
        "priority_items": weeklog.priority_items.all(),
        "absences": weeklog.absences.all(),
        "incidents": weeklog.incidents.all(),
    }

    try:
        body_html = render_to_string("logbook/exports/email_body.html", context)
    except Exception as e:
        return False, f"Fejl ved generering af email-indhold: {e}"

    # Generate PDF attachment
    try:
        pdf_content = generate_pdf(weeklog)
    except Exception as e:
        return False, f"Fejl ved generering af PDF: {e}"

    # Create email
    subject = f"FynBus IT Ugelog - {weeklog.week_label}"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "it@fynbus.dk")

    email = EmailMessage(
        subject=subject,
        body=body_html,
        from_email=from_email,
        to=recipients,
    )
    email.content_subtype = "html"

    # Attach PDF
    filename = f"ugelog_{weeklog.year}_uge{weeklog.week_number}.pdf"
    email.attach(filename, pdf_content, "application/pdf")

    # Send email
    try:
        email.send(fail_silently=False)
        return True, f"Email sendt til {len(recipients)} modtager(e)."
    except Exception as e:
        return False, f"Fejl ved afsendelse af email: {e}"
