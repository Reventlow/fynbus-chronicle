"""Week log delopgave stats (1.27.0): how many delopgaver on vulnerability sager
are open and how many wait on a vendor. Live while the week runs, a frozen
snapshot once it has ended, nothing for weeks that were never recorded."""

import re
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone

from apps.cves.models import CVECase, CVETask, vuln_task_stats, weeklog_cves
from apps.logbook.exports.email import send_weeklog_email
from apps.logbook.exports.html import generate_html
from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.exports.pdf import generate_pdf
from apps.logbook.models import WeekLog


def _week(offset_weeks: int = 0) -> WeekLog:
    iso = (timezone.localdate() + timedelta(weeks=offset_weeks)).isocalendar()
    return WeekLog.objects.create(year=iso.year, week_number=iso.week)


@pytest.fixture
def vuln(editor):
    return CVECase.objects.create(title="OpenSSH", created_by=editor)


@pytest.fixture
def tasks(vuln, editor):
    """Two open, one waiting on a patch, one on a release, one done."""
    for title in ("Opdatér web01", "Opdatér web02"):
        CVETask.add(vuln, title=title, user=editor)
    CVETask.add(vuln, title="Firewall", user=editor, status=CVETask.Status.WAITING_PATCH)
    CVETask.add(vuln, title="Switch", user=editor, status=CVETask.Status.WAITING_RELEASE)
    CVETask.add(vuln, title="Printer", user=editor, status=CVETask.Status.DONE)


def test_counts_open_and_waiting_on_vulnerability_sager_only(tasks, editor):
    incident = CVECase.objects.create(title="Nedbrud", kind=CVECase.Kind.INCIDENT, created_by=editor)
    CVETask.add(incident, title="Ikke en sårbarhed", user=editor)
    assert vuln_task_stats() == {"open": 2, "waiting": 2}


def test_running_week_shows_live_counts_and_records_them(tasks):
    week = _week()
    assert weeklog_cves(week)["week_task_stats"] == {"open": 2, "waiting": 2}
    week.refresh_from_db()
    assert (week.vuln_tasks_open, week.vuln_tasks_waiting) == (2, 2)


def test_task_changes_update_the_running_week(vuln, editor):
    week = _week()
    task = CVETask.add(vuln, title="Opdatér", user=editor)
    week.refresh_from_db()
    assert (week.vuln_tasks_open, week.vuln_tasks_waiting) == (1, 0)
    task.set_status(CVETask.Status.WAITING_PATCH, editor)
    week.refresh_from_db()
    assert (week.vuln_tasks_open, week.vuln_tasks_waiting) == (0, 1)
    task.remove(editor)
    week.refresh_from_db()
    assert (week.vuln_tasks_open, week.vuln_tasks_waiting) == (0, 0)


def test_ended_week_keeps_its_snapshot(tasks):
    week = _week(-1)
    WeekLog.objects.filter(pk=week.pk).update(vuln_tasks_open=7, vuln_tasks_waiting=3)
    week.refresh_from_db()
    assert weeklog_cves(week)["week_task_stats"] == {"open": 7, "waiting": 3}
    week.refresh_from_db()
    assert (week.vuln_tasks_open, week.vuln_tasks_waiting) == (7, 3)  # not overwritten with today's 2/2


def test_task_changes_leave_ended_weeks_alone(vuln, editor):
    week = _week(-1)
    CVETask.add(vuln, title="Opdatér", user=editor)
    week.refresh_from_db()
    assert week.vuln_tasks_open is None


def test_unrecorded_week_shows_nothing(tasks):
    assert weeklog_cves(_week(-1))["week_task_stats"] is None


def test_snapshot_does_not_bump_updated_at(tasks):
    week = _week()
    before = week.updated_at
    weeklog_cves(week)
    week.refresh_from_db()
    assert week.updated_at == before


def _stats_line(html: str) -> str:
    """The stats row's text, tags and whitespace collapsed."""
    start = html.index("Delopgaver på sårbarheder")
    return " ".join(re.sub(r"<[^>]+>", " ", html[start:html.index("</tr>", start)]).replace("&nbsp;", " ")
                    .replace("&middot;", "·").split())


def test_html_and_markdown_exports_show_the_stats(tasks):
    week = _week()
    assert _stats_line(generate_html(week)) == "Delopgaver på sårbarheder 2 åbne · 2 venter på leverandør"
    assert "**Delopgaver på sårbarheder:** 2 åbne · 2 venter på leverandør" in generate_markdown(week)


def test_pdf_export_shows_the_stats(tasks):
    """What WeasyPrint is handed for the PDF download."""
    week = _week()
    with patch("weasyprint.HTML") as html_cls:
        html_cls.return_value.write_pdf.return_value = b"%PDF"
        generate_pdf(week)
    rendered = html_cls.call_args.kwargs["string"]
    assert _stats_line(rendered) == "Delopgaver på sårbarheder 2 åbne · 2 venter på leverandør"


@pytest.mark.parametrize("fmt", ["html", "both"])
def test_email_body_shows_the_stats(tasks, settings, fmt):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]
    week = _week()
    with patch("apps.logbook.exports.email.generate_pdf", return_value=b"%PDF"):
        ok, message = send_weeklog_email(week, format=fmt, from_email="it@fynbus.dk")
    assert ok, message
    assert _stats_line(mail.outbox[0].body) == "Delopgaver på sårbarheder 2 åbne · 2 venter på leverandør"
