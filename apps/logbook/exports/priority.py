"""Export functions for a single priority item's history.

Mirrors the weeklog export setup (PDF / Markdown / HTML / email) but
scoped to one ``PriorityItem`` and its appearance history. Same shape
of output channels editors are already used to from the weeklog export
dropdown — see ``apps.logbook.exports.{pdf,markdown,html,email}``.
"""

from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from ..models import PriorityItem


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _slug_for_filename(item: PriorityItem) -> str:
    """A safe filename stem for the item — id + truncated slug-ish title."""
    safe = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in item.title.lower()
    ).strip("_")[:48] or "opgave"
    return f"opgavelog_{item.pk}_{safe}"


def _appearances(item: PriorityItem):
    return (
        item.appearances.select_related("weeklog")
        .order_by("-weeklog__year", "-weeklog__week_number")
    )


def _context(item: PriorityItem) -> dict:
    return {
        "item": item,
        "appearances": _appearances(item),
        "appearance_count": item.appearances.count(),
        "generated_at": datetime.now(),
    }


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def generate_priority_markdown(item: PriorityItem) -> str:
    """Generate a Markdown document for a single priority item's history."""
    lines: list[str] = []
    lines.append(f"# Opgavelog: {item.title}")
    lines.append("")
    lines.append(f"**Status:** {item.get_status_display()}")
    lines.append(f"**Prioritet:** {item.get_priority_display()}")
    lines.append(f"**Opstod:** {item.origin_weeklog.week_label}")
    lines.append(f"**Sidst aktiv:** {item.last_active_at.strftime('%d. %B %Y · %H:%M')}")
    if item.auto_closed:
        lines.append("**Auto-lukket:** Ja (6+ uger uden aktivitet)")
    if item.is_deleted:
        lines.append(f"**Slettet:** {item.deleted_at.strftime('%d. %B %Y')}")
    if item.is_merged and item.merged_into_id:
        lines.append(f"**Flettet ind i:** {item.merged_into.title} (#{item.merged_into_id})")
    lines.append(f"**Genereret:** {datetime.now().strftime('%d. %B %Y · %H:%M')}")
    lines.append("")

    if item.notes:
        lines.append("## Noter")
        lines.append("")
        lines.append(item.notes)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"## Tidslinje ({item.appearances.count()} uge(r))")
    lines.append("")

    appearances = _appearances(item)
    if not appearances:
        lines.append("_Ingen historik registreret._")
        return "\n".join(lines) + "\n"

    for a in appearances:
        lines.append(f"### {a.weeklog.week_label}")
        lines.append("")
        lines.append(f"_Tilføjet {a.created_at.strftime('%d. %b %Y · %H:%M')}_")
        lines.append("")
        if a.description:
            lines.append(a.description)
        else:
            lines.append("_Ingen ugebeskrivelse._")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


# Browser-only overlay on top of the same shared pdf_styles.css used by the
# weekly report — keeps download HTML consistent with the rest of the app.
_BROWSER_CSS = """
body { max-width: 800px; margin: 0 auto; padding: 30px 40px; background: #FFFFFF; }
img { max-width: 100%; height: auto; }
.section { margin: 20px 0; }
"""


def _render_report_html(item: PriorityItem, with_browser_css: bool = False) -> str:
    """Render the shared HTML report. Optionally append browser-only CSS."""
    html = render_to_string("logbook/exports/priority_report.html", _context(item))
    if not with_browser_css:
        return html
    # Inject the browser overlay just before </head>. Safe because the
    # template controls its own <head>.
    return html.replace("</head>", f"<style>{_BROWSER_CSS}</style></head>", 1)


def generate_priority_html(item: PriorityItem) -> str:
    return _render_report_html(item, with_browser_css=True)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def generate_priority_pdf(item: PriorityItem) -> bytes:
    """Render the report through WeasyPrint, applying pdf_styles.css."""
    try:
        from weasyprint import CSS, HTML
    except ImportError as e:  # pragma: no cover — dependency must exist in prod
        raise ImportError(
            "WeasyPrint is required for PDF generation."
        ) from e

    html_content = _render_report_html(item, with_browser_css=False)
    css_path = settings.BASE_DIR / "static" / "css" / "pdf_styles.css"

    html = HTML(string=html_content)
    css = CSS(filename=str(css_path)) if css_path.exists() else None
    return html.write_pdf(stylesheets=[css] if css else None)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def send_priority_email(
    item: PriorityItem, format: str = "both", from_email: str | None = None
) -> tuple[bool, str]:
    """Send the priority history report via email. Same format options as
    the weeklog email exporter (``html`` / ``pdf`` / ``both``)."""
    if format not in ("html", "pdf", "both"):
        return False, f"Ugyldigt format: {format}. Brug 'html', 'pdf' eller 'both'."

    recipients = getattr(settings, "CHRONICLE_EMAIL_RECIPIENTS", [])
    if not recipients:
        return False, "Ingen email-modtagere konfigureret. Tjek CHRONICLE_EMAIL_RECIPIENTS."

    subject = f"FynBus IT Opgavelog — {item.title}"
    if not from_email:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "it@fynbus.dk")

    if format == "pdf":
        body = (
            f"FynBus IT Opgavelog — {item.title}\n\n"
            "Rapporten er vedhæftet som PDF."
        )
        email = EmailMessage(subject=subject, body=body, from_email=from_email, to=recipients)
    else:
        try:
            body_html = _render_report_html(item, with_browser_css=False)
        except Exception as e:  # pragma: no cover
            return False, f"Fejl ved generering af email-indhold: {e}"
        email = EmailMessage(subject=subject, body=body_html, from_email=from_email, to=recipients)
        email.content_subtype = "html"

    if format in ("pdf", "both"):
        try:
            pdf_bytes = generate_priority_pdf(item)
        except Exception as e:  # pragma: no cover
            return False, f"Fejl ved generering af PDF: {e}"
        email.attach(f"{_slug_for_filename(item)}.pdf", pdf_bytes, "application/pdf")

    try:
        email.send(fail_silently=False)
    except Exception as e:
        return False, f"Fejl ved afsendelse af email: {e}"

    label = {"html": "HTML", "pdf": "PDF", "both": "HTML + PDF"}[format]
    return True, f"Email ({label}) sendt til {len(recipients)} modtager(e)."


# Re-export the filename helper so views can use it consistently.
slug_for_filename = _slug_for_filename
