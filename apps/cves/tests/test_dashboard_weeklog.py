"""The Kontrolpanel CVE card and the computed CVE section of the week log."""

from datetime import datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVE
from apps.dashboard.overview import cve_overview
from apps.logbook.exports.html import generate_html
from apps.logbook.models import WeekLog

pytestmark = pytest.mark.django_db


def _age(cve, days):
    old = timezone.now() - timedelta(days=days)
    CVE.objects.filter(pk=cve.pk).update(updated_at=old, created_at=old)


class TestDashboardCard:
    def test_overview_counts_and_order(self, editor):
        patching = CVE.objects.create(cve_id="CVE-2026-3001", subject="patcher")
        patching.set_state(CVE.State.PATCHING, editor)
        identified = CVE.objects.create(cve_id="CVE-2026-3002", subject="ny")
        solved = CVE.objects.create(cve_id="CVE-2026-3003", subject="løst")
        solved.set_state(CVE.State.SOLVED, editor)
        forgotten = CVE.objects.create(cve_id="CVE-2026-3004", subject="glemt")
        _age(forgotten, 60)

        data = cve_overview()
        assert data["cves"] == [patching, identified, solved]
        assert data["open_count"] == 3  # the forgotten one still counts as open
        assert data["solved_count"] == 1

    def test_partial_renders(self, editor_client, cve):
        response = editor_client.get(reverse("dashboard:partial-cves"))
        assert response.status_code == 200
        body = response.content.decode()
        assert cve.cve_id in body
        assert reverse("cves:detail", args=[cve.pk]) in body
        assert reverse("cves:list") in body
        assert "1 åben, 0 løst" in body

    def test_partial_empty_state(self, editor_client):
        body = editor_client.get(reverse("dashboard:partial-cves")).content.decode()
        assert "Ingen CVE&#x27;er de sidste 30 dage." in body or "Ingen CVE'er de sidste 30 dage." in body

    def test_index_loads_card(self, editor_client):
        body = editor_client.get(reverse("dashboard:index")).content.decode()
        assert reverse("dashboard:partial-cves") in body

    def test_viewer_can_read(self, viewer_client, cve):
        assert viewer_client.get(reverse("dashboard:partial-cves")).status_code == 200


class TestWeeklogSection:
    @pytest.fixture
    def weeklog(self):
        return WeekLog.objects.create(year=2026, week_number=20)

    @staticmethod
    def at(y, m, d, h=12):
        return timezone.make_aware(datetime(y, m, d, h))

    def test_section_lists_open_and_solved_this_week(self, editor_client, weeklog):
        still_open = CVE.objects.create(cve_id="CVE-2026-4001", subject="åben", created_at=self.at(2026, 5, 4))
        solved = CVE.objects.create(cve_id="CVE-2026-4002", subject="løst", created_at=self.at(2026, 5, 4))
        CVE.objects.filter(pk=solved.pk).update(state="solved", solved_at=self.at(2026, 5, 14))
        CVE.objects.create(cve_id="CVE-2026-4003", subject="senere", created_at=self.at(2026, 5, 20))

        response = editor_client.get(reverse("logbook:weeklog-detail", args=[2026, 20]))
        assert response.status_code == 200
        week_cves = response.context["week_cves"]
        assert {c.cve_id for c in week_cves} == {still_open.cve_id, solved.cve_id}
        body = response.content.decode()
        assert "CVE-2026-4001" in body
        assert "CVE-2026-4002" in body
        assert "CVE-2026-4003" not in body
        assert "Løst denne uge" in body

    def test_solved_cve_gone_next_week(self, editor_client, weeklog):
        WeekLog.objects.create(year=2026, week_number=21)
        solved = CVE.objects.create(cve_id="CVE-2026-4010", subject="løst", created_at=self.at(2026, 5, 4))
        CVE.objects.filter(pk=solved.pk).update(state="solved", solved_at=self.at(2026, 5, 14))
        response = editor_client.get(reverse("logbook:weeklog-detail", args=[2026, 21]))
        assert response.context["week_cves"] == []
        assert "Ingen åbne CVE" in response.content.decode()

    def test_html_export_includes_section(self, weeklog):
        CVE.objects.create(cve_id="CVE-2026-4020", subject="i eksporten", cvss="8.1", created_at=self.at(2026, 5, 4))
        html = generate_html(weeklog)
        assert "CVE-2026-4020" in html
        assert "CVSS 8,1" in html  # Danish decimal comma
