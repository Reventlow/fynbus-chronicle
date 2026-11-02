"""Week log export visibility (1.15.1, 1.15.2): a case with every "Vis i
ugelogs-eksport" box off is not listed in the export, but the export's
chart still counts it; the week log page still lists it. CVEs have no section
of their own in the export; a shown case still names its CVEs."""

import re
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

    def test_export_chart_counts_hidden_cases(self, week20, shown, hidden):
        summary = {r["label"]: (r["open"], r["solved"]) for r in weeklog_cves(week20)["week_summary"]}
        assert summary["Sårbarheder"] == (2, 0)
        html = generate_html(week20)
        assert re.search(r"Sårbarheder</td>.*?<strong>2</strong> <span[^>]*>åbne</span>", html, re.S)

    def test_chart_but_no_rows_when_every_case_is_hidden(self, week20, hidden):
        html = generate_html(week20)
        assert "<h2>Sårbarheder og hændelser</h2>" in html
        assert re.search(r"Sårbarheder</td>.*?<strong>1</strong> <span[^>]*>åbne</span>", html, re.S)
        assert "Intern Synology-sag" not in html

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


class TestMailExport:
    """The mail (HTML body, PDF attachment, or both) follows the same rules
    as the HTML/PDF export: shown cases in, hidden cases and loose CVEs out."""

    @pytest.fixture(autouse=True)
    def recipients(self, settings):
        settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]

    @pytest.fixture
    def loose(self):
        return CVE.objects.create(cve_id="CVE-2026-5099", subject="løs", created_at=at(2026, 5, 11))

    @pytest.fixture(autouse=True)
    def minutes(self, week20):
        week20.meeting_minutes = "Punkt 1"
        week20.save()

    def _send(self, week, fmt):
        from django.core import mail

        from apps.logbook.exports.email import send_weeklog_email

        ok, message = send_weeklog_email(week, format=fmt, from_email="gorm@fynbus.dk")
        assert ok, message
        return mail.outbox[-1]

    @pytest.mark.parametrize("fmt", ["html", "both"])
    def test_html_body(self, week20, shown, hidden, loose, fmt):
        body = self._send(week20, fmt).body
        assert "<h2>Sårbarheder og hændelser</h2>" in body
        assert "Synlig kerne-sag" in body and "CVE-2026-5001" in body
        assert "Intern Synology-sag" not in body
        assert re.search(r"Sårbarheder</td>.*?<strong>2</strong> <span[^>]*>åbne</span>", body, re.S)
        assert "CVE-2026-5099" not in body
        assert "data:image" not in body  # still Outlook-safe
        # Same liggetid-style chart, in the mail's font size, before the minutes.
        assert re.search(r"<strong>0</strong> <span[^>]*>færdigbehandlet</span>", body)
        assert "font-size:13px; color:#4A4540; font-weight:600" in body
        assert body.index("<h2>Sårbarheder og hændelser</h2>") < body.index("Referat af mandags møde")

    @pytest.mark.parametrize("fmt", ["pdf", "both"])
    def test_pdf_attachment(self, week20, shown, hidden, loose, fmt, monkeypatch):
        # The attached PDF is rendered from the same HTML as the export;
        # capture that HTML instead of parsing the PDF bytes.
        import apps.logbook.exports.pdf as pdf_module

        seen = {}
        real = pdf_module.render_to_string

        def capture(name, context=None, *a, **kw):
            html = real(name, context, *a, **kw)
            if name == "logbook/exports/weekly_report.html":
                seen["html"] = html
            return html

        monkeypatch.setattr(pdf_module, "render_to_string", capture)
        msg = self._send(week20, fmt)
        assert any(att[0].endswith(".pdf") for att in msg.attachments if isinstance(att, tuple))
        html = seen["html"]
        assert "Synlig kerne-sag" in html and "CVE-2026-5001" in html
        assert "Intern Synology-sag" not in html and "CVE-2026-5099" not in html


class TestChartLayout:
    def test_chart_rows_and_position(self, week20, shown, hidden):
        week20.summary = "Rolig uge."
        week20.meeting_minutes = "Punkt 1"
        week20.save()
        html = generate_html(week20)
        # Liggetid-style grid: count + word on the right, one framed table.
        assert re.search(r"<strong>2</strong> <span[^>]*>åbne</span>", html)
        assert re.search(r"<strong>0</strong> <span[^>]*>færdigbehandlet</span>", html)
        # The section sits before the meeting minutes.
        assert html.index("<h2>Sårbarheder og hændelser</h2>") < html.index("Referat af mandags møde")

    def test_no_stray_dot_when_meta_line_starts_with_solved(self, editor, week20):
        CVECase.objects.create(kind="incident", title="VPN", created_at=at(2026, 5, 11),
                               state="solved", solved_at=at(2026, 5, 13))
        html = generate_html(week20)
        assert "Færdigbehandlet denne uge" in html
        assert not re.search(r">\s*&middot; Færdigbehandlet denne uge", html)
