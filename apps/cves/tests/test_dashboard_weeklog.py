"""The Kontrolpanel CVE card and the computed CVE section of the week log."""

from datetime import datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVE, CVECase
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
        assert "1 åben CVE, 0 færdigbehandlet" in body
        assert "Ingen åbne sager" in body
        assert reverse("cves:case-list") in body

    def test_partial_empty_state(self, editor_client):
        body = editor_client.get(reverse("dashboard:partial-cves")).content.decode()
        assert "Ingen sager eller CVE&#x27;er de sidste 30 dage." in body or "Ingen sager eller CVE'er de sidste 30 dage." in body

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
        assert "Færdigbehandlet denne uge" in body

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


class TestCasesWithoutCVEs:
    """A CFCS warning without a CVE number is a case with no CVEs; it must
    still reach the Kontrolpanel and the week log (the NIS2 trail)."""

    @staticmethod
    def at(y, m, d, h=12):
        return timezone.make_aware(datetime(y, m, d, h))

    @pytest.fixture
    def cfcs(self, editor):
        return CVECase.objects.create(title="CFCS: phishing mod trafikselskaber", source="CFCS",
                                      reference="CFCS-advarsel 2026-10-24", created_by=editor,
                                      created_at=self.at(2026, 5, 12))

    def test_dashboard_lists_open_cases_first(self, editor_client, cfcs, cve):
        data = cve_overview()
        assert data["cases"] == [cfcs]
        assert data["open_case_count"] == 1
        body = editor_client.get(reverse("dashboard:partial-cves")).content.decode()
        assert cfcs.get_absolute_url() in body
        assert "CFCS-advarsel 2026-10-24" in body
        assert body.index(cfcs.get_absolute_url()) < body.index(reverse("cves:detail", args=[cve.pk]))

    def test_dashboard_keeps_recently_solved_cases_only(self, editor, cfcs):
        cfcs.set_state(CVE.State.SOLVED, editor, resolution=CVECase.Resolution.NOT_AFFECTED)
        data = cve_overview()
        assert data["cases"] == [cfcs] and data["open_case_count"] == 0
        CVECase.objects.filter(pk=cfcs.pk).update(solved_at=timezone.now() - timedelta(days=31))
        assert cve_overview()["cases"] == []

    def test_dashboard_nests_cves_under_their_case(self, editor, editor_client, cve):
        case = CVECase.objects.create(title="Kerne, oktober", created_by=editor)
        case.add_cves([cve], editor)
        loose = CVE.objects.create(cve_id="CVE-2026-5005", subject="uden sag")
        data = cve_overview()
        assert data["cases"] == [case] and list(data["cases"][0].cves.all()) == [cve]
        assert data["cves"] == [loose]  # the case's CVE is shown under the case, not again
        body = editor_client.get(reverse("dashboard:partial-cves")).content.decode()
        detail = reverse("cves:detail", args=[cve.pk])
        assert body.count(detail) == 1
        assert body.index(case.get_absolute_url()) < body.index(detail) < body.index("CVE'er uden sag") < body.index(loose.cve_id)

    def test_dashboard_card_shows_with_only_a_case(self, editor_client, cfcs):
        body = editor_client.get(reverse("dashboard:partial-cves")).content.decode()
        assert cfcs.title in body
        assert "Ingen CVE" not in body.split(cfcs.title)[0]  # no empty-state above the case

    def test_week_log_lists_the_case(self, editor_client, cfcs):
        WeekLog.objects.create(year=2026, week_number=20)
        later = CVECase.objects.create(title="senere", created_at=self.at(2026, 5, 20))
        response = editor_client.get(reverse("logbook:weeklog-detail", args=[2026, 20]))
        assert response.context["week_cases"] == [cfcs]
        assert response.context["week_vuln_count"] == 1
        body = response.content.decode()
        assert cfcs.get_absolute_url() in body
        assert "CFCS-advarsel 2026-10-24" in body
        assert "Ingen åbne CVE" not in body
        assert later.title not in body

    def test_case_solved_this_week_is_marked(self, editor_client, cfcs):
        WeekLog.objects.create(year=2026, week_number=20)
        CVECase.objects.filter(pk=cfcs.pk).update(state="solved", resolution="not_affected",
                                                  solved_at=self.at(2026, 5, 14))
        response = editor_client.get(reverse("logbook:weeklog-detail", args=[2026, 20]))
        assert response.context["week_cases"][0].solved_this_week
        assert "Færdigbehandlet denne uge" in response.content.decode()

    def test_html_export_includes_cases(self, cfcs):
        html = generate_html(WeekLog.objects.create(year=2026, week_number=20))
        assert "sag #%d" % cfcs.pk in html
        assert "CFCS-advarsel 2026-10-24" in html
        assert "Ingen CVE" in html
