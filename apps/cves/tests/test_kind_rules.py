"""1.26.0: only sårbarhedssager hold CVEs, hændelser get their own fields,
delopgaver can be edited and deleted, and editors land on "Mine" delopgaver.
"""

import importlib
import json
from datetime import date, datetime, timedelta

import pytest
from django.apps import apps as django_apps
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVE, CaseKindHoldsNoCVEs, CVECase, CVETask


def at(*args) -> datetime:
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def case(editor):
    return CVECase.objects.create(title="PHP session", created_by=editor)


@pytest.fixture
def incident(editor):
    return CVECase.objects.create(title="Phishing-kampagne", kind=CVECase.Kind.INCIDENT, created_by=editor)


@pytest.fixture
def planned(editor):
    return CVECase.objects.create(title="Licensfornyelse", kind=CVECase.Kind.TASK, created_by=editor)


class TestOnlyVulnerabilitySagerHoldCVEs:
    def test_model_refuses(self, incident, planned, cve, editor):
        for sag in (incident, planned):
            with pytest.raises(CaseKindHoldsNoCVEs):
                sag.add_cves([cve], editor)
        cve.refresh_from_db()
        assert cve.case_id is None

    def test_add_view_refuses(self, editor_client, incident):
        response = editor_client.post(reverse("cves:case-add-cves", args=[incident.pk]), {"cve_ids": "CVE-2026-1234"})
        assert response.status_code == 302
        assert not CVE.objects.filter(cve_id="CVE-2026-1234").exists()

    def test_join_from_a_cve_refuses(self, editor_client, incident, cve):
        response = editor_client.post(reverse("cves:join-case", args=[cve.pk]), {"case": incident.pk})
        assert response.url == cve.get_absolute_url()
        cve.refresh_from_db()
        assert cve.case_id is None

    def test_cve_page_offers_only_vulnerability_sager(self, editor_client, case, incident, planned, cve):
        response = editor_client.get(cve.get_absolute_url())
        assert list(response.context["open_cases"]) == [case]

    def test_new_cve_form_offers_only_vulnerability_sager(self, editor_client, case, incident, planned):
        form = editor_client.get(reverse("cves:create")).context["form"]
        assert list(form.fields["sag"].queryset) == [case]

    def test_create_incident_with_cves_is_refused(self, editor_client):
        response = editor_client.post(reverse("cves:case-create"),
                                      {"kind": "incident", "title": "Nede", "cve_ids": "CVE-2026-1234"})
        assert response.status_code == 200
        assert "kan ikke have CVE" in response.content.decode()
        assert not CVECase.objects.exists() and not CVE.objects.exists()

    def test_sag_with_cves_cannot_become_an_incident(self, editor_client, case, cve, editor):
        case.add_cves([cve], editor)
        response = editor_client.post(reverse("cves:case-edit", args=[case.pk]), {"kind": "incident", "title": case.title})
        assert response.status_code == 200 and "ud af sagen først" in response.content.decode()
        case.refresh_from_db()
        assert case.kind == CVECase.Kind.VULNERABILITY

    def test_incident_page_has_no_cve_card(self, editor_client, incident):
        body = editor_client.get(incident.get_absolute_url()).content.decode()
        assert 'id="cves"' not in body and reverse("cves:case-add-cves", args=[incident.pk]) not in body

    def test_api_refuses_cves_on_an_incident(self, client, incident, write_key):
        response = client.post(reverse("api:cve-case-list"), content_type="application/json",
                               data=json.dumps({"id": incident.pk, "cves": [{"cve_id": "CVE-2026-1234", "subject": "Test"}]}),
                               HTTP_AUTHORIZATION=f"Bearer {write_key}")
        assert response.status_code == 400 and response.json()["field"] == "cves"
        assert not CVE.objects.exists()


class TestIncidentFields:
    def post_incident(self, editor_client, **extra):
        data = {"kind": "incident", "title": "VPN nede", "cve_ids": "", "occurred_at": "2026-11-20T08:15",
                "severity": "high", "affected": "Alle fjernbrugere", **extra}
        return editor_client.post(reverse("cves:case-create"), data)

    def test_saved_on_an_incident(self, editor_client):
        self.post_incident(editor_client)
        case = CVECase.objects.get()
        assert (case.occurred_at, case.severity, case.affected) == (at(2026, 11, 20, 8, 15), "high", "Alle fjernbrugere")

    def test_blanked_on_other_kinds(self, editor_client):
        self.post_incident(editor_client, kind="vulnerability")
        case = CVECase.objects.get()
        assert (case.occurred_at, case.severity, case.affected) == (None, "", "")

    def test_shown_on_the_sag(self, editor_client):
        self.post_incident(editor_client)
        body = editor_client.get(CVECase.objects.get().get_absolute_url()).content.decode()
        assert "Tidspunkt" in body and "Høj" in body and "Alle fjernbrugere" in body

    def test_not_shown_on_a_vulnerability(self, editor_client, case):
        assert "incident-facts" not in editor_client.get(case.get_absolute_url()).content.decode()

    def test_edit_form_keeps_the_time(self, editor_client):
        """datetime-local needs ISO; the Danish locale format would show an empty field (and lose it on save)."""
        self.post_incident(editor_client)
        body = editor_client.get(reverse("cves:case-edit", args=[CVECase.objects.get().pk])).content.decode()
        assert 'value="2026-11-20T08:15"' in body

    def test_form_follows_the_type_radio(self, editor_client):
        body = editor_client.get(reverse("cves:case-create") + "?kind=incident").content.decode()
        assert "x-show=\"kind === 'incident'\"" in body and "x-show=\"kind === 'vulnerability'\"" in body
        assert "Nyt planlagt arbejde" in body  # the headings travel to Alpine
        assert "<h1" in body and ">Ny hændelse</span>" in body

    def test_backfill_from_the_assessment_line(self, editor):
        old = CVECase.objects.create(kind=CVECase.Kind.INCIDENT, title="Gammel", created_by=editor,
                                     created_at=at(2026, 3, 2, 9),
                                     assessment="Nede.\n\n*Type: Systemfejl · Alvorlighed: Kritisk · Tidspunkt: 02.03.2026 09:00*")
        plain = CVECase.objects.create(kind=CVECase.Kind.INCIDENT, title="Uden", created_by=editor)
        vuln = CVECase.objects.create(title="Sårbarhed", created_by=editor, assessment="Alvorlighed: Høj")
        migration = importlib.import_module("apps.cves.migrations.0014_incident_fields")
        migration.backfill(django_apps, None)
        for c in (old, plain, vuln):
            c.refresh_from_db()
        assert (old.occurred_at, old.severity) == (at(2026, 3, 2, 9), "critical")
        assert (plain.occurred_at, plain.severity) == (plain.created_at, "")
        assert (vuln.occurred_at, vuln.severity) == (None, "")
        assert old.assessment.startswith("Nede.")  # the text is left alone

    def test_api_payload_has_the_fields(self, client, write_key):
        from apps.logbook.models import WeekLog

        WeekLog.objects.create(year=2026, week_number=47)
        response = client.post(reverse("api:incident-create", args=[2026, 47]), content_type="application/json",
                               data=json.dumps({"title": "Print nede", "description": "Ingen print.", "severity": "low",
                                                "affected": "Administrationen", "occurred_at": "2026-11-18T10:00:00+01:00"}),
                               HTTP_AUTHORIZATION=f"Bearer {write_key}")
        payload = response.json()["case"]
        assert (payload["severity"], payload["affected"]) == ("low", "Administrationen")
        assert payload["occurred_at"].startswith("2026-11-18T")


class TestEditDelopgaver:
    def test_edit_changes_and_logs(self, editor_client, case, editor):
        other = editor.__class__.objects.create_user("kollega", password="x", first_name="Kim")
        task = CVETask.add(case, title="Opdatér", user=editor)
        response = editor_client.post(reverse("cves:case-task-edit", args=[case.pk, task.pk]),
                                      {"title": "Opdatér til 8.5.13", "assignee": other.pk, "due_date": "2026-12-01"})
        assert response.url == case.get_absolute_url() + "#opgaver"
        task.refresh_from_db()
        assert (task.title, task.assignee, task.due_date) == ("Opdatér til 8.5.13", other, date(2026, 12, 1))
        line = case.comments.order_by("-id").first().text
        assert line.startswith("Delopgave ændret: Opdatér til 8.5.13 — titel: Opdatér → Opdatér til 8.5.13")
        assert "ansvarlig: ingen → Kim" in line and "frist: ingen → 01.12.2026" in line

    def test_unchanged_logs_nothing(self, editor_client, case, editor):
        task = CVETask.add(case, title="Opdatér", user=editor)
        before = case.comments.count()
        editor_client.post(reverse("cves:case-task-edit", args=[case.pk, task.pk]), {"title": "Opdatér"})
        assert case.comments.count() == before

    def test_empty_title_is_refused_and_keeps_next(self, editor_client, case, editor):
        task = CVETask.add(case, title="Opdatér", user=editor)
        response = editor_client.post(reverse("cves:case-task-edit", args=[case.pk, task.pk]),
                                      {"title": " ", "next": "/cves/tasks/"})
        assert response.url == case.get_absolute_url() + "?next=%2Fcves%2Ftasks%2F#opgaver"
        task.refresh_from_db()
        assert task.title == "Opdatér"

    def test_inactive_assignee_can_be_kept(self, editor_client, case, editor):
        gone = editor.__class__.objects.create_user("stoppet", password="x", is_active=False)
        task = CVETask.add(case, title="Opdatér", user=editor, assignee=gone)
        response = editor_client.post(reverse("cves:case-task-edit", args=[case.pk, task.pk]),
                                      {"title": "Opdatér nu", "assignee": gone.pk})
        task.refresh_from_db()
        assert response.url.endswith("#opgaver") and (task.title, task.assignee) == ("Opdatér nu", gone)
        assert "(inaktiv)" in editor_client.get(case.get_absolute_url()).content.decode()

    def test_delete_logs_and_reapplies_the_gate(self, editor_client, case, editor):
        done = CVETask.add(case, title="Gjort", user=editor, status=CVETask.Status.DONE)
        left = CVETask.add(case, title="Glemt", user=editor)
        case.refresh_from_db()
        assert case.state == CVE.State.PATCHING
        editor_client.post(reverse("cves:case-task-delete", args=[case.pk, left.pk]))
        case.refresh_from_db()
        assert list(case.tasks.all()) == [done] and case.state == CVE.State.REVIEW
        assert case.comments.filter(text="Delopgave slettet: Glemt (Åben)").exists()

    def test_viewers_cannot(self, viewer_client, case, editor):
        task = CVETask.add(case, title="Opdatér", user=editor)
        assert viewer_client.post(reverse("cves:case-task-edit", args=[case.pk, task.pk]), {"title": "x"}).status_code == 403
        assert viewer_client.post(reverse("cves:case-task-delete", args=[case.pk, task.pk])).status_code == 403
        assert CVETask.objects.get().title == "Opdatér"

    def test_task_of_another_sag_is_404(self, editor_client, case, incident, editor):
        task = CVETask.add(incident, title="Andet", user=editor)
        assert editor_client.post(reverse("cves:case-task-delete", args=[case.pk, task.pk])).status_code == 404

    def test_sag_page_offers_it(self, editor_client, case, editor):
        task = CVETask.add(case, title="Opdatér", user=editor)
        body = editor_client.get(case.get_absolute_url()).content.decode()
        assert "Rediger eller slet" in body and reverse("cves:case-task-delete", args=[case.pk, task.pk]) in body


class TestMineIsTheDefault:
    @pytest.fixture
    def tasks(self, case, editor):
        other = editor.__class__.objects.create_user("kollega", password="x")
        CVETask.add(case, title="Min", user=editor, assignee=editor)
        CVETask.add(case, title="Kollegas", user=editor, assignee=other,
                    due_date=timezone.localdate() + timedelta(days=3))

    def titles(self, response):
        return sorted(t.title for t in response.context["tasks"])

    def test_editor_lands_on_mine(self, editor_client, tasks):
        response = editor_client.get(reverse("cves:task-list"))
        assert response.context["mine"] and self.titles(response) == ["Min"]
        assert 'href="?status=active&amp;mine=0"' in response.content.decode()

    def test_alle_shows_everyone(self, editor_client, tasks):
        response = editor_client.get(reverse("cves:task-list") + "?mine=0")
        assert not response.context["mine"] and self.titles(response) == ["Kollegas", "Min"]
        assert 'href="?status=overdue&amp;mine=0"' in response.content.decode()  # tiles keep the scope

    def test_viewer_lands_on_everyone(self, viewer_client, tasks):
        response = viewer_client.get(reverse("cves:task-list"))
        assert not response.context["mine"] and self.titles(response) == ["Kollegas", "Min"]


class TestReviewFixes:
    """Found in review before 1.26.0 shipped."""

    def test_cve_error_is_visible_on_an_incident(self, editor_client):
        body = editor_client.post(reverse("cves:case-create"),
                                  {"kind": "incident", "title": "Nede", "cve_ids": "CVE-2026-1234"}).content.decode()
        assert 'class="alert alert-error"><p>Hændelse kan ikke have CVE' in body

    def test_hidden_cve_field_is_not_sent(self, editor_client):
        body = editor_client.get(reverse("cves:case-create")).content.decode()
        assert 'x-bind:disabled="kind !== &#x27;vulnerability&#x27;"' in body  # entities decode in the attribute

    def test_older_incident_with_cves_can_still_be_edited(self, editor_client, incident, cve):
        CVE.objects.filter(pk=cve.pk).update(case=incident)  # from before 1.26.0
        response = editor_client.post(reverse("cves:case-edit", args=[incident.pk]), {"kind": "incident", "title": "Nyt navn"})
        assert response.status_code == 302
        incident.refresh_from_db()
        assert incident.title == "Nyt navn"
        body = editor_client.get(incident.get_absolute_url()).content.decode()
        assert 'id="cves"' in body and reverse("cves:case-remove-cve", args=[incident.pk, cve.pk]) in body
        assert f'action="{reverse("cves:case-add-cves", args=[incident.pk])}"' not in body

    def test_deleting_the_only_open_task_releases_the_sag(self, editor_client, case, editor):
        task = CVETask.add(case, title="Eneste", user=editor)
        case.refresh_from_db()
        assert case.state == CVE.State.PATCHING
        editor_client.post(reverse("cves:case-task-delete", args=[case.pk, task.pk]))
        case.refresh_from_db()
        assert case.state == CVE.State.REVIEW and not case.tasks.exists()

    def test_deleting_a_task_on_a_manual_sag_keeps_its_state(self, editor_client, case, editor):
        task = CVETask.add(case, title="Gjort", user=editor, status=CVETask.Status.DONE)
        case.set_state(CVE.State.IDENTIFIED, editor)
        editor_client.post(reverse("cves:case-task-delete", args=[case.pk, task.pk]))
        case.refresh_from_db()
        assert case.state == CVE.State.IDENTIFIED

    def test_incident_facts(self, incident, case):
        incident.occurred_at, incident.severity, incident.affected = at(2026, 11, 20, 8, 15), "high", "Alle"
        assert incident.incident_facts == "Tidspunkt 20.11.2026 08:15 · Alvorlighed: Høj · Berørte: Alle"
        case.severity = "high"
        assert case.incident_facts == ""

    def test_week_export_shows_the_facts(self, incident):
        from django.template.loader import render_to_string

        incident.occurred_at, incident.severity = at(2026, 11, 20, 8, 15), "critical"
        incident.save()
        html = render_to_string("logbook/exports/_week_cases.html",
                                {"week_cases": [incident], "export_cases": [incident], "week_summary": {}})
        assert "Tidspunkt 20.11.2026 08:15 · Alvorlighed: Kritisk" in html

    def test_admin_offers_only_vulnerability_sager(self, case, incident):
        from django.contrib import admin as django_admin

        model_admin = django_admin.site._registry[CVE]
        field = model_admin.formfield_for_foreignkey(CVE._meta.get_field("case"), None)
        assert list(field.queryset) == [case]


class TestTextEditsOnTheTimeline:
    def lines(self, case):
        return list(case.comments.filter(kind="state").order_by("id").values_list("text", flat=True))

    def test_edit_form_logs_written_changed_and_cleared(self, editor_client, case):
        url = reverse("cves:case-edit", args=[case.pk])
        editor_client.post(url, {"kind": "vulnerability", "title": case.title, "assessment": "Berørt.", "solution": ""})
        editor_client.post(url, {"kind": "vulnerability", "title": case.title, "assessment": "Ikke berørt.",
                                 "solution": "Patch"})
        editor_client.post(url, {"kind": "vulnerability", "title": case.title, "assessment": "", "solution": "Patch"})
        assert self.lines(case) == ["Vurdering skrevet", "Vurdering ændret", "Løsning / handling skrevet",
                                    "Vurdering slettet"]

    def test_unchanged_text_logs_nothing(self, editor_client, case):
        case.assessment = "Berørt."
        case.save()
        editor_client.post(reverse("cves:case-edit", args=[case.pk]),
                           {"kind": "vulnerability", "title": "Ny titel", "assessment": "Berørt.  "})
        assert self.lines(case) == []

    def test_api_update_logs(self, client, case, write_key):
        client.post(reverse("api:cve-case-list"), content_type="application/json",
                    data=json.dumps({"id": case.pk, "solution": "Opdateret til 8.5"}),
                    HTTP_AUTHORIZATION=f"Bearer {write_key}")
        assert self.lines(case) == ["Løsning / handling skrevet"]

    def test_lines_stay_out_of_the_week_export(self, editor_client, case):
        editor_client.post(reverse("cves:case-edit", args=[case.pk]),
                           {"kind": "vulnerability", "title": case.title, "assessment": "Berørt."})
        assert case.comments.get().kind == "state"  # the export lists only kind=comment
