"""Incidents as cases (1.12.0): case type, the per-section "Vis i
ugelogs-eksport" boxes, the week log chart, and the retired logbook
Hændelser (read-only archive, Kontrolpanel card gone, API makes a case)."""

import json
from datetime import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVE, CVECase, CVEComment, CVELink, weeklog_cves
from apps.logbook.exports.html import generate_html
from apps.logbook.models import Incident, WeekLog

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


def at(y, m, d, h=12):
    return timezone.make_aware(datetime(y, m, d, h))


@pytest.fixture(autouse=True)
def cve_files(settings, tmp_path):
    settings.CVE_FILES_DIR = tmp_path / "cve_files"


@pytest.fixture
def week20():
    """ISO week 20 of 2026 runs Mon 11 May – Sun 17 May."""
    return WeekLog.objects.create(year=2026, week_number=20)


@pytest.fixture
def incident(editor):
    return CVECase.objects.create(kind=CVECase.Kind.INCIDENT, title="Puzzel nede", assessment="Telefoni nede i 40 min.",
                                  solution="Leverandøren genstartede.", created_by=editor, created_at=at(2026, 5, 12))


class TestKind:
    def test_default_is_vulnerability(self, editor):
        case = CVECase.objects.create(title="x")
        assert case.kind == CVECase.Kind.VULNERABILITY and not case.is_incident

    def test_incident_says_under_behandling(self, editor, incident):
        assert incident.set_state(CVE.State.PATCHING, editor)
        assert incident.outcome_label == "Under behandling"

    def test_incident_page_has_incident_buttons(self, editor_client, incident):
        body = editor_client.get(incident.get_absolute_url()).content.decode()
        assert "Hændelse · sag #" in body and "Under behandling" in body
        assert "Færdigbehandlet — patchet" not in body
        assert "CVE&#x27;er i sagen" not in body and "CVE'er i sagen" not in body  # no CVE card on an incident

    def test_new_incident_button_prefills_the_type(self, editor_client):
        body = editor_client.get(reverse("cves:case-create") + "?kind=incident").content.decode()
        assert 'value="incident" id="id_kind_1" checked' in body
        assert "Ny hændelse" in editor_client.get(reverse("cves:case-list")).content.decode()

    def test_create_incident_via_form(self, editor_client):
        editor_client.post(reverse("cves:case-create"), {"kind": "incident", "title": "VPN nede", "cve_ids": ""})
        assert CVECase.objects.get().kind == CVECase.Kind.INCIDENT

    def test_create_incident_helper(self, editor):
        case = CVECase.create_incident(title="Backup", description="Manglende kopier.", user=editor,
                                       occurred_at=at(2026, 10, 21, 8), type_label="Andet", severity_label="Høj",
                                       resolved=True, resolution="Kopier genskabt.", solved_at=at(2026, 10, 22))
        assert (case.kind, case.state, case.solved_at, case.created_at) == ("incident", "solved", at(2026, 10, 22), at(2026, 10, 21, 8))
        assert case.assessment.startswith("Manglende kopier.") and "Type: Andet · Alvorlighed: Høj" in case.assessment
        assert case.solution == "Kopier genskabt."


class TestExportToggles:
    def test_defaults(self, incident):
        assert (incident.export_assessment, incident.export_solution) == (True, True)
        assert not (incident.export_comments or incident.export_links or incident.export_attachments)

    def test_page_shows_a_box_per_section(self, editor_client, incident):
        body = editor_client.get(incident.get_absolute_url()).content.decode()
        for section in CVECase.EXPORT_SECTIONS:
            assert reverse("cves:case-export-toggle", args=[incident.pk, section]) in body
        assert body.count("Vis i ugelogs-eksport") == 5

    def test_editor_flips_a_box(self, editor_client, incident):
        response = editor_client.post(reverse("cves:case-export-toggle", args=[incident.pk, "comments"]))
        assert response.status_code == 200 and "checked" in response.content.decode()
        incident.refresh_from_db()
        assert incident.export_comments
        editor_client.post(reverse("cves:case-export-toggle", args=[incident.pk, "comments"]))
        incident.refresh_from_db()
        assert not incident.export_comments

    def test_unknown_section_is_404(self, editor_client, incident):
        assert editor_client.post(reverse("cves:case-export-toggle", args=[incident.pk, "title"])).status_code == 404

    def test_viewer_cannot_flip(self, viewer_client, incident):
        assert viewer_client.post(reverse("cves:case-export-toggle", args=[incident.pk, "links"])).status_code in (302, 403)
        incident.refresh_from_db()
        assert not incident.export_links
        body = viewer_client.get(incident.get_absolute_url()).content.decode()
        assert "Ikke i ugelogs-eksport" in body and 'type="checkbox"' not in body.split("Vurdering")[1][:400]


class TestWeekExport:
    def test_shows_only_ticked_sections(self, editor, editor_client, week20, incident, cve_files):
        CVEComment.objects.create(case=incident, author=editor, text="Kommentar i uge 20")
        CVEComment.objects.filter(case=incident).update(created_at=at(2026, 5, 13))
        CVEComment.objects.create(case=incident, author=editor, text="Kommentar fra en anden uge")  # now: not week 20
        CVELink.objects.create(case=incident, url="https://status.example/puzzel", label="Statusside")
        editor_client.post(incident.owner_url("attachment-create"), {
            "file": SimpleUploadedFile("rapport.pdf", PDF, content_type="application/pdf"), "title": "Hændelsesrapport",
            "tlp": "amber"}, HTTP_HX_REQUEST="true")

        html = generate_html(week20)
        assert "Hændelse &middot; sag #%d" % incident.pk in html
        assert "Telefoni nede i 40 min." in html and "Leverandøren genstartede." in html
        assert "Kommentar i uge 20" not in html and "Statusside" not in html and "Hændelsesrapport" not in html

        CVECase.objects.filter(pk=incident.pk).update(export_comments=True, export_links=True, export_attachments=True,
                                                      export_solution=False)
        html = generate_html(week20)
        assert "Kommentar i uge 20" in html and "Kommentar fra en anden uge" not in html
        assert "Statusside" in html and "Hændelsesrapport" in html and "TLP:AMBER" in html
        assert "Leverandøren genstartede." not in html
        assert "/attachments/" not in html  # files are named, never linked

    def test_chart_counts_per_kind(self, editor, week20, incident):
        CVECase.objects.create(title="Kerne", created_at=at(2026, 5, 11))
        CVECase.objects.create(title="PHP", created_at=at(2026, 5, 11), state="solved", solved_at=at(2026, 5, 14))
        CVECase.objects.create(kind="incident", title="VPN", created_at=at(2026, 5, 11), state="solved",
                               solved_at=at(2026, 5, 20))  # solved after the week: still open at its end
        summary = {r["label"]: (r["open"], r["solved"]) for r in weeklog_cves(week20)["week_summary"]}
        assert summary == {"Hændelser": (2, 0), "Sårbarheder": (1, 1)}
        html = generate_html(week20)
        assert "Sårbarheder og hændelser" in html and "Åbne = stadig åbne ved ugens udgang" in html


class TestIncidentsRetired:
    def test_logbook_incident_views_are_gone(self, editor_client, week20):
        assert editor_client.get(reverse("logbook:incident-create") + f"?weeklog={week20.pk}").status_code == 410
        old = Incident.objects.create(weeklog=week20, title="Gammel", description="x")
        assert editor_client.get(reverse("logbook:incident-edit", args=[old.pk])).status_code == 410
        assert editor_client.delete(reverse("logbook:incident-delete", args=[old.pk])).status_code == 410
        assert Incident.objects.filter(pk=old.pk).exists()

    def test_week_log_shows_old_incidents_read_only(self, editor_client, week20):
        url = reverse("logbook:weeklog-detail", args=[2026, 20])
        assert "Hændelser · arkiv" not in editor_client.get(url).content.decode()
        old = Incident.objects.create(weeklog=week20, title="Gammel hændelse", description="x")
        body = editor_client.get(url).content.decode()
        assert "Hændelser · arkiv" in body and "Gammel hændelse" in body
        assert reverse("logbook:incident-create") not in body
        assert reverse("logbook:incident-edit", args=[old.pk]) not in body

    def test_kontrolpanel_has_no_incidents_card(self, editor, editor_client, incident):
        body = editor_client.get(reverse("dashboard:index")).content.decode()
        assert reverse("dashboard:partial-incidents") not in body
        assert "Sårbarheder og hændelser" in body
        headline = editor_client.get(reverse("dashboard:partial-headline")).content.decode() \
            if _has_url("dashboard:partial-headline") else body
        assert "åbne" in headline

    def test_api_incident_creates_an_incident_case(self, client, write_key):
        WeekLog.objects.create(year=2026, week_number=44)
        response = client.post(reverse("api:incident-create", args=[2026, 44]), content_type="application/json",
                               data=json.dumps({"title": "Exchange nede", "description": "Mail ude i 1 t.",
                                                "severity": "high", "incident_type": "system", "resolved": True,
                                                "resolution": "MS løste det."}),
                               HTTP_AUTHORIZATION=f"Bearer {write_key}")
        assert response.status_code == 201
        case = CVECase.objects.get()
        assert (case.kind, case.state, case.solution) == ("incident", "solved", "MS løste det.")
        assert "Type: Systemfejl · Alvorlighed: Høj" in case.assessment
        data = response.json()
        assert data["incident"]["id"] == case.pk and data["case"]["kind"] == "incident"
        assert not Incident.objects.exists()


def _has_url(name: str) -> bool:
    from django.urls import NoReverseMatch
    try:
        reverse(name)
        return True
    except NoReverseMatch:
        return False
