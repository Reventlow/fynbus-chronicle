"""Week log export visibility (1.15.1): a case with every "Vis i
ugelogs-eksport" box off is left out of the export entirely (and out of
its chart), while the week log page still lists it. CVEs have no section
of their own in the export; a shown case still names its CVEs."""

from datetime import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVE, CVECase, weeklog_cves
from apps.logbook.exports.html import generate_html
from apps.logbook.models import WeekLog

pytestmark = pytest.mark.django_db

ALL_OFF = dict(export_assessment=False, export_solution=False, export_comments=False,
               export_links=False, export_attachments=False)


def at(y, m, d, h=12):
    return timezone.make_aware(datetime(y, m, d, h))


@pytest.fixture
def week20():
    return WeekLog.objects.create(year=2026, week_number=20)


@pytest.fixture
def shown(editor):
    case = CVECase.objects.create(title="Synlig kerne-sag", created_at=at(2026, 5, 11), created_by=editor)
    case.add_cves([CVE.objects.create(cve_id="CVE-2026-5001", subject="kerne", created_at=at(2026, 5, 11))], editor)
    return case


@pytest.fixture
def hidden(editor):
    return CVECase.objects.create(title="Intern Synology-sag", created_at=at(2026, 5, 11), created_by=editor, **ALL_OFF)


class TestCaseVisibility:
    def test_in_week_export(self, shown, hidden):
        assert shown.in_week_export and not hidden.in_week_export
        CVECase.objects.filter(pk=hidden.pk).update(export_links=True)
        hidden.refresh_from_db()
        assert hidden.in_week_export  # any one box is enough

    def test_hidden_case_left_out_of_export(self, week20, shown, hidden):
        html = generate_html(week20)
        assert "Synlig kerne-sag" in html
        assert "Intern Synology-sag" not in html
        assert f"sag #{hidden.pk}" not in html

    def test_export_chart_counts_only_shown_cases(self, week20, shown, hidden):
        ctx = weeklog_cves(week20)
        page = {r["label"]: (r["open"], r["solved"]) for r in ctx["week_summary"]}
        export = {r["label"]: (r["open"], r["solved"]) for r in ctx["export_summary"]}
        assert page["Sårbarheder"] == (2, 0)
        assert export["Sårbarheder"] == (1, 0)

    def test_no_section_when_every_case_is_hidden(self, week20, hidden):
        assert "<h2>Sårbarheder og hændelser</h2>" not in generate_html(week20)

    def test_page_still_lists_hidden_case(self, editor_client, week20, shown, hidden):
        body = editor_client.get(reverse("logbook:weeklog-detail", args=[2026, 20])).content.decode()
        assert "Intern Synology-sag" in body and "Synlig kerne-sag" in body


class TestNoCveSection:
    def test_shown_case_names_its_cve_but_no_cve_section(self, week20, shown):
        html = generate_html(week20)
        assert "CVE-2026-5001" in html  # in the case row
        assert "<h2>CVE'er</h2>" not in html and "<h2>CVE&#x27;er</h2>" not in html

    def test_hidden_case_cves_not_exported(self, editor, week20, hidden):
        hidden.add_cves([CVE.objects.create(cve_id="CVE-2024-10441", subject="Synology", created_at=at(2026, 5, 11))], editor)
        assert "CVE-2024-10441" not in generate_html(week20)
