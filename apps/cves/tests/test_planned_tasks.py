"""Planned tasks (1.15.0): a third case type next to Sårbarheder and
Hændelser, with its own state words (Planlagt / I gang / Udført), an
optional due date, and a type icon on every case row."""

from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVE, CVECase, weeklog_cves
from apps.logbook.models import WeekLog


def at(y, m, d, h=12):
    return timezone.make_aware(datetime(y, m, d, h))


@pytest.fixture
def task(editor):
    return CVECase.objects.create(kind=CVECase.Kind.TASK, title="Portainer EE: licens og 3.x",
                                  due_date=date(2026, 12, 15), created_by=editor)


class TestTaskKind:
    def test_state_words(self, editor, task):
        assert task.is_task and not task.is_vulnerability and task.outcome_label == "Planlagt"
        assert task.set_state(CVE.State.PATCHING, editor)
        assert task.outcome_label == "I gang"
        assert task.set_state(CVE.State.SOLVED, editor)
        assert task.outcome_label == "Udført"

    def test_overdue(self, task):
        assert not task.is_overdue
        task.due_date = timezone.localdate() - timedelta(days=1)
        assert task.is_overdue
        task.state = CVE.State.SOLVED
        assert not task.is_overdue

    def test_page_has_task_buttons_and_no_cve_card(self, editor_client, task):
        body = editor_client.get(task.get_absolute_url()).content.decode()
        assert "Planlagt opgave · sag #" in body and "case-kind-task" in body
        assert ">I gang<" in body and ">Udført<" in body and "Patcher" not in body
        assert "Frist 15. " in body and "2026" in body
        assert "CVE&#x27;er i sagen" not in body and "CVE'er i sagen" not in body

    def test_new_task_button_prefills_the_type(self, editor_client):
        assert "Ny planlagt opgave" in editor_client.get(reverse("cves:case-list")).content.decode()
        body = editor_client.get(reverse("cves:case-create") + "?kind=task").content.decode()
        assert 'value="task" id="id_kind_2" checked' in body and 'name="due_date"' in body

    def test_create_task_via_form(self, editor_client):
        editor_client.post(reverse("cves:case-create"), {"kind": "task", "title": "Opgrader Portainer",
                                                         "due_date": "2026-12-15", "cve_ids": ""})
        case = CVECase.objects.get()
        assert (case.kind, case.due_date) == ("task", date(2026, 12, 15))


class TestKontrolpanel:
    def test_icons_tell_the_types_apart(self, editor_client, editor, task):
        CVECase.objects.create(title="Brotli", created_by=editor)
        CVECase.objects.create(kind=CVECase.Kind.INCIDENT, title="VPN nede", created_by=editor)
        body = editor_client.get(reverse("dashboard:partial-cves")).content.decode()
        for kind in ("vulnerability", "incident", "task"):
            assert f"case-kind-icon case-kind-{kind}" in body

    def test_headline_counts_open_tasks(self, editor_client, task):
        body = editor_client.get(reverse("dashboard:partial-headline")).content.decode()
        assert "planlagte opgave" in body


class TestWeekChart:
    def test_tasks_row_only_when_there_are_tasks(self, editor):
        week = WeekLog.objects.create(year=2026, week_number=20)
        CVECase.objects.create(title="Kerne", created_at=at(2026, 5, 11))
        assert [r["label"] for r in weeklog_cves(week)["week_summary"]] == ["Hændelser", "Sårbarheder"]
        CVECase.objects.create(kind="task", title="Licens", created_at=at(2026, 5, 11))
        summary = {r["label"]: (r["open"], r["solved"]) for r in weeklog_cves(week)["week_summary"]}
        assert summary["Planlagte opgaver"] == (1, 0)
