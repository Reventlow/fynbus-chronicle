"""
Markdown export functionality for week logs.

Generates a Markdown document from a WeekLog instance. The content
mirrors the PDF/HTML download and the mail (weekly_report.html and
email_body.html) section for section, without the charts;
apps/logbook/tests/test_export_parity.py keeps them in step.
"""

from django.utils import dateformat, timezone

from apps.courses.templatetags.course_tags import (
    markdown_links as course_markdown_links,
)
from apps.cves.models import weeklog_cves
from apps.oncall.models import OnCallDuty, OnCallSegment
from apps.planner.templatetags.planner_tags import markdown_links
from apps.servicedesk.templatetags.servicedesk_tags import (
    markdown_links as ticket_markdown_links,
)

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
    now = timezone.localtime()
    lines.append(f"**Genereret:** {dateformat.format(now, 'd. F Y H:i')}")
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
        f"**Lukkede sager:** {weeklog.helpdesk_closed} | "
        f"**Åbne sager:** {weeklog.helpdesk_open} | "
        f"**Netto ændring:** {delta_str}"
    )
    lines.append("")
    avgs = WeekLog.helpdesk_weekly_averages()
    if avgs["avg_new"] is not None and avgs["avg_closed"] is not None:
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
            "åbne sager har ligget i mere end 1 måned."
        )
        lines.append("")

    # Open tickets by category at the end of the week
    open_categories = weeklog.helpdesk_open_by_category()
    if open_categories["total"]:
        lines.append("### Åbne sager fordelt på kategori")
        lines.append("")
        lines.append("| Kategori | Antal | Andel |")
        lines.append("| --- | ---: | ---: |")
        for category in open_categories["categories"]:
            lines.append(
                f"| {category['label']} | {category['count']} | {category['share']:.0f}% |"
            )
        lines.append("")

    # Open tickets by technician at the end of the week
    open_technicians = weeklog.helpdesk_open_by_technician()
    if open_technicians["total"]:
        lines.append("### Åbne sager fordelt på tekniker")
        lines.append("")
        lines.append("| Tekniker | Antal | Andel |")
        lines.append("| --- | ---: | ---: |")
        for technician in open_technicians["technicians"]:
            lines.append(
                f"| {technician['label']} | {technician['count']} | {technician['share']:.0f}% |"
            )
        lines.append("")

    # Summary
    if weeklog.summary:
        lines.append("## Ugeoversigt")
        lines.append("")
        lines.append(f"> {weeklog.summary}")
        lines.append("")

    lines.extend(_week_cases(weeklog))

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
        weeklog.priority_appearances.select_related("priority_item")
        .prefetch_related("priority_item__planner_links", "priority_item__ticket_links", "priority_item__course_links__folder", "priority_item__course_links__material__folder").order_by("order", "id")
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
                f"| {item.title}{markdown_links(item)}{ticket_markdown_links(item)}{course_markdown_links(item)} | {item.get_priority_display()} | "
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
    lines.append(f"*FynBus IT Chronicle | Genereret {dateformat.format(now, 'd/m/Y H:i')}*")

    return "\n".join(lines)


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def _week_cases(weeklog: WeekLog) -> list[str]:
    """"Sårbarheder og hændelser", as in _week_cases.html: the per-kind
    counts (every case), then each case its export boxes allow, with only
    the parts those boxes allow. Attachments by name and TLP only."""
    ctx = weeklog_cves(weeklog)
    if not ctx["week_cases"]:
        return []
    lines = ["## Sårbarheder og hændelser", "",
             "| | Åbne | Færdigbehandlet |", "| --- | ---: | ---: |"]
    for row in ctx["week_summary"]:
        lines.append(f"| {row['label']} | {row['open']} | {row['solved']} |")
    lines += ["", "*Åbne = stadig åbne ved ugens udgang. Færdigbehandlet = færdigbehandlet i løbet af ugen.*", ""]
    for case in ctx["export_cases"]:
        lines.append(
            f"### {case.get_kind_display()} · sag #{case.pk} · {case.title}"
            f"{markdown_links(case)}{ticket_markdown_links(case)}{course_markdown_links(case)}"
        )
        lines.append("")
        facts = [f"**Status:** {case.outcome_label}"]
        if case.source:
            facts.append(case.source_label)
        if case.reference:
            facts.append(case.reference)
        cves = [f"`{c.cve_id}`" for c in case.cves.all()]
        if cves:
            facts.append(", ".join(cves))
        elif case.is_vulnerability:
            facts.append("Ingen CVE")
        if case.solved_this_week:
            facts.append("Færdigbehandlet denne uge")
        lines += [" · ".join(facts), ""]
        if case.export_assessment and case.assessment:
            lines += [f"**Vurdering:** {case.assessment}", ""]
        if case.export_solution and case.solution:
            lines += [f"**Løsning / handling:** {case.solution}", ""]
        if case.week_comments:
            lines.append("**Kommentarer denne uge:**")
            for c in case.week_comments:
                who = f" · {c.author.get_full_name() or c.author.username}" if c.author else ""
                when = dateformat.format(timezone.localtime(c.created_at), "d/m H:i")
                lines.append(f"- {when}{who}: {_one_line(c.text)}")
            lines.append("")
        if case.export_links_list:
            lines.append("**Links:**")
            lines += [f"- [{link.label or link.url}]({link.url})" for link in case.export_links_list]
            lines.append("")
        if case.export_attachments_list:
            lines.append("**Vedhæftninger** *(hentes i Chronicle)*:")
            lines += [f"- {a.display_title}" + (f" · **{a.get_tlp_display()}**" if a.tlp else "")
                      for a in case.export_attachments_list]
            lines.append("")
    return lines
