"""
Markdown export functionality for week logs.

Generates a Markdown document from a WeekLog instance.
"""

from datetime import datetime

from ..models import WeekLog


def generate_markdown(weeklog: WeekLog) -> str:
    """
    Generate a Markdown document for a week log.

    Args:
        weeklog: The WeekLog instance to export.

    Returns:
        Markdown formatted string.
    """
    lines = []

    # Header
    lines.append(f"# FynBus IT Ugelog - {weeklog.week_label}")
    lines.append("")
    lines.append(f"*Genereret: {datetime.now().strftime('%d. %B %Y %H:%M')}*")
    lines.append("")

    # Helpdesk statistics
    lines.append("## Helpdesk Statistik")
    lines.append("")
    lines.append("| Metrik | Antal |")
    lines.append("|--------|-------|")
    lines.append(f"| Nye sager | {weeklog.helpdesk_new} |")
    lines.append(f"| Lukkede sager | {weeklog.helpdesk_closed} |")
    lines.append(f"| Åbne sager | {weeklog.helpdesk_open} |")
    delta = weeklog.helpdesk_delta
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    lines.append(f"| Netto ændring | {delta_str} |")
    lines.append("")

    # Summary
    if weeklog.summary:
        lines.append("## Ugeoversigt")
        lines.append("")
        lines.append(weeklog.summary)
        lines.append("")

    # Priority items
    priority_items = weeklog.priority_items.all()
    if priority_items:
        lines.append("## Prioriterede Opgaver")
        lines.append("")
        for item in priority_items:
            # Show each item as a subsection
            lines.append(f"### {item.title}")
            lines.append("")
            lines.append(f"**Prioritet:** {item.get_priority_display()} | **Status:** {item.get_status_display()}")
            lines.append("")
            if item.description:
                lines.append(item.description)
                lines.append("")
            if item.notes:
                lines.append(f"**Noter:** {item.notes}")
                lines.append("")

    # Absences
    absences = weeklog.absences.all()
    if absences:
        lines.append("## Fravær")
        lines.append("")
        lines.append("| Medarbejder | Type | Periode |")
        lines.append("|-------------|------|---------|")
        for absence in absences:
            period = f"{absence.start_date.strftime('%d/%m')} - {absence.end_date.strftime('%d/%m/%Y')}"
            lines.append(
                f"| {absence.staff_name} | {absence.get_absence_type_display()} | {period} |"
            )
        lines.append("")

    # Incidents
    incidents = weeklog.incidents.all()
    if incidents:
        lines.append("## Hændelser")
        lines.append("")
        for incident in incidents:
            status = "Løst" if incident.resolved else "Uløst"
            lines.append(
                f"### {incident.title} ({incident.get_severity_display()}) - {status}"
            )
            lines.append("")
            lines.append(
                f"**Type:** {incident.get_incident_type_display()} | "
                f"**Tidspunkt:** {incident.occurred_at.strftime('%d/%m/%Y %H:%M')}"
            )
            lines.append("")
            lines.append(incident.description)
            lines.append("")
            if incident.resolution:
                lines.append(f"**Løsning:** {incident.resolution}")
                lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*FynBus IT Chronicle*")

    return "\n".join(lines)
