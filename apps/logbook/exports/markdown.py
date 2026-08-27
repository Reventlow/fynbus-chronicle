"""
Markdown export functionality for week logs.

Generates a Markdown document from a WeekLog instance.
"""

from datetime import datetime

from apps.oncall.models import OnCallDuty, OnCallSegment

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
    lines.append("# FynBus IT Ugelog")
    lines.append("")
    lines.append(f"**Periode:** {weeklog.week_label}")
    lines.append(f"**Genereret:** {datetime.now().strftime('%d. %B %Y %H:%M')}")
    oncall = OnCallDuty.get_for_week(weeklog.year, weeklog.week_number)
    oncall_split = OnCallSegment.split_week_display(weeklog.year, weeklog.week_number)
    if oncall_split:
        lines.append(f"**Rådighedsvagt:** {oncall_split}")
    elif oncall:
        lines.append(f"**Rådighedsvagt:** {oncall.user.get_full_name() or oncall.user.username}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Helpdesk statistics
    lines.append("## Helpdesk Statistik")
    lines.append("")
    delta = weeklog.helpdesk_delta
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    lines.append(
        f"**Nye sager:** {weeklog.helpdesk_new} | "
        f"**Lukkede:** {weeklog.helpdesk_closed} | "
        f"**Åbne:** {weeklog.helpdesk_open} | "
        f"**Netto:** {delta_str}"
    )
    lines.append("")
    avgs = WeekLog.helpdesk_weekly_averages()
    lines.append(
        f"**Gns. nye/uge:** {avgs['avg_new']} | "
        f"**Gns. lukkede/uge:** {avgs['avg_closed']}"
    )
    lines.append("")

    # Liggetid — open tickets by age, as a plain table
    if weeklog.has_helpdesk_age_breakdown:
        lines.append("### Åbne sager fordelt på liggetid")
        lines.append("")
        lines.append("| Liggetid | Antal | Andel |")
        lines.append("| --- | ---: | ---: |")
        for bucket in weeklog.helpdesk_age_buckets:
            lines.append(
                f"| {bucket['label']} | {bucket['count']} | {bucket['share']:.0f}% |"
            )
        lines.append("")
        lines.append(
            f"{weeklog.helpdesk_open_stale} af {weeklog.helpdesk_open_bucketed} "
            "åbne sager har ligget i mere end 30 dage."
        )
        lines.append("")

    # Summary
    if weeklog.summary:
        lines.append("## Ugeoversigt")
        lines.append("")
        lines.append(f"> {weeklog.summary}")
        lines.append("")

    # Meeting minutes
    if weeklog.meeting_skipped:
        lines.append("## Referat af mandags møde")
        lines.append("")
        reason = weeklog.meeting_skipped_reason or ""
        lines.append(f"*Mødet blev ikke afholdt denne uge.*{' ' + reason if reason else ''}")
        lines.append("")
    elif weeklog.meeting_attendees or weeklog.meeting_minutes:
        lines.append("## Referat af mandags møde")
        lines.append("")
        if weeklog.meeting_attendees:
            lines.append(f"**Deltagere:** {weeklog.meeting_attendees}")
            lines.append("")
        if weeklog.meeting_minutes:
            lines.append(weeklog.meeting_minutes)
            lines.append("")

    # Priority items — iterate appearances so we get this week's description.
    appearances = list(
        weeklog.priority_appearances.select_related("priority_item").order_by("order", "id")
    )
    if appearances:
        lines.append("## Prioriterede Opgaver")
        lines.append("")
        lines.append("| Opgave | Prioritet | Status | Beskrivelse |")
        lines.append("|--------|-----------|--------|-------------|")
        for a in appearances:
            item = a.priority_item
            desc = a.description or "-"
            desc = desc.replace("\n", " ").replace("\r", "")
            lines.append(
                f"| {item.title} | {item.get_priority_display()} | "
                f"{item.get_status_display()} | {desc} |"
            )
        lines.append("")

        items_with_notes = [a.priority_item for a in appearances if a.priority_item.notes]
        if items_with_notes:
            lines.append("### Noter")
            lines.append("")
            for item in items_with_notes:
                lines.append(f"**{item.title}:** {item.notes}")
                lines.append("")

    # Absences
    absences = weeklog.absences.all()
    if absences:
        lines.append("## Bemanding")
        lines.append("")
        lines.append("| Medarbejder | Type | Fra | Til | Dage | Noter |")
        lines.append("|-------------|------|-----|-----|------|-------|")
        for absence in absences:
            notes = absence.notes or "-"
            lines.append(
                f"| {absence.staff_name} | {absence.get_absence_type_display()} | "
                f"{absence.start_date.strftime('%d/%m')} | {absence.end_date.strftime('%d/%m')} | "
                f"{absence.duration_days} | {notes} |"
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
                f"### {incident.title}"
            )
            lines.append("")
            lines.append(
                f"**Alvorlighed:** {incident.get_severity_display()} | "
                f"**Status:** {status} | "
                f"**Type:** {incident.get_incident_type_display()}"
            )
            lines.append(f"**Tidspunkt:** {incident.occurred_at.strftime('%d/%m/%Y %H:%M')}")
            lines.append("")
            lines.append(incident.description)
            lines.append("")
            if incident.resolution:
                lines.append(f"**Løsning:** {incident.resolution}")
                lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*FynBus IT Chronicle | Genereret {datetime.now().strftime('%d/%m/%Y %H:%M')}*")

    return "\n".join(lines)
