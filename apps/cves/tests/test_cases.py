"""CVE cases: CVEs grouped under one assessment, fix and set of documents.

Model rules (state follows the case, one case per CVE), the case pages and
inline documents, the CVE page's case controls, and the API Harbinger uses.
"""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.cves.models import CVE, CaseConflict, CVEAttachment, CVECase, CVEComment, CVELink

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


@pytest.fixture
def editor_client(editor):
    """Own session: conftest's editor_client and viewer_client share one Client."""
    c = Client()
    c.force_login(editor)
    return c


@pytest.fixture
def viewer_client(viewer):
    c = Client()
    c.force_login(viewer)
    return c


@pytest.fixture(autouse=True)
def cve_files(settings, tmp_path):
    settings.CVE_FILES_DIR = tmp_path / "cve_files"
    return settings.CVE_FILES_DIR


@pytest.fixture
def kernel(editor):
    """Two kernel CVEs, as on 2026-10-24."""
    return [
        CVE.objects.create(cve_id="CVE-2026-93228", subject="svcrdma chunk validation", cvss="9.1", created_by=editor),
        CVE.objects.create(cve_id="CVE-2026-93207", subject="SUNRPC RPCSEC_GSS reuse", cvss="9.8", created_by=editor),
    ]


@pytest.fixture
def case(editor, kernel):
    case = CVECase.objects.create(title="Linux-kerne, oktober 2026", created_by=editor)
    case.add_cves(kernel, editor)
    return case


def timeline(obj) -> list[str]:
    return [c.text for c in obj.comments.order_by("created_at", "id")]


# -------------------------------------------------------------------------
# Model
# -------------------------------------------------------------------------


class TestModel:
    def test_added_cves_take_the_case_state_and_note_it(self, editor, kernel):
        case = CVECase.objects.create(title="Kerne", state=CVE.State.PATCHING)
        added = case.add_cves(kernel, editor)
        assert added == kernel
        for cve in kernel:
            cve.refresh_from_db()
            assert (cve.case, cve.state) == (case, CVE.State.PATCHING)
            assert f"Føjet til sag #{case.pk}: Kerne" in timeline(cve)
        assert timeline(case) == ["Tilføjet: CVE-2026-93228, CVE-2026-93207"]

    def test_adding_again_is_a_no_op(self, case, kernel, editor):
        assert case.add_cves(kernel, editor) == []

    def test_state_change_moves_every_cve(self, case, kernel, editor):
        assert case.set_state(CVE.State.SOLVED, editor, resolution=CVECase.Resolution.PATCHED)
        case.refresh_from_db()
        assert (case.state, case.resolution, case.solved_by) == ("solved", "patched", editor)
        assert case.outcome_label == "Færdigbehandlet — patchet"
        for cve in kernel:
            cve.refresh_from_db()
            assert cve.state == CVE.State.SOLVED and cve.solved_at
            assert timeline(cve)[-1] == f"Status: Identificeret → Færdigbehandlet (via sag #{case.pk})"
        assert timeline(case)[-1] == "Status: Identificeret → Færdigbehandlet — patchet"

    def test_changing_only_the_resolution_counts(self, case, editor):
        case.set_state(CVE.State.SOLVED, editor, resolution="patched")
        assert case.set_state(CVE.State.SOLVED, editor, resolution="not_affected")
        assert timeline(case)[-1] == "Status: Færdigbehandlet — patchet → Færdigbehandlet — ikke berørt"
        assert not case.set_state(CVE.State.SOLVED, editor, resolution="not_affected")

    def test_risk_accepted_is_an_outcome(self, case, kernel, editor):
        assert case.set_state(CVE.State.SOLVED, editor, resolution=CVECase.Resolution.RISK_ACCEPTED)
        case.refresh_from_db()
        assert case.outcome_label == "Færdigbehandlet — risiko accepteret"
        assert timeline(case)[-1] == "Status: Identificeret → Færdigbehandlet — risiko accepteret"
        assert all(c.state == CVE.State.SOLVED for c in CVE.objects.filter(case=case))

    def test_reopening_clears_resolution_and_solved_stamp(self, case, editor):
        case.set_state(CVE.State.SOLVED, editor, resolution="patched")
        case.set_state(CVE.State.PATCHING, editor, resolution="patched")
        case.refresh_from_db()
        assert (case.resolution, case.solved_at, case.solved_by) == ("", None, None)

    def test_a_cve_belongs_to_one_case(self, case, kernel, editor):
        other = CVECase.objects.create(title="Andet")
        with pytest.raises(CaseConflict):
            other.add_cves([kernel[0]], editor)
        assert other.cves.count() == 0

    def test_conflict_adds_nothing(self, case, kernel, editor):
        free = CVE.objects.create(cve_id="CVE-2026-0001", subject="x")
        other = CVECase.objects.create(title="Andet")
        with pytest.raises(CaseConflict):
            other.add_cves([free, kernel[0]], editor)
        free.refresh_from_db()
        assert free.case is None

    def test_remove_keeps_the_cve_state(self, case, kernel, editor):
        case.set_state(CVE.State.PATCHING, editor)
        assert case.remove_cve(kernel[0], editor)
        kernel[0].refresh_from_db()
        assert (kernel[0].case, kernel[0].state) == (None, CVE.State.PATCHING)
        assert timeline(case)[-1] == "Fjernet: CVE-2026-93228"

    def test_deleting_a_case_frees_its_cves(self, case, kernel):
        case.delete()
        kernel[0].refresh_from_db()
        assert kernel[0].case is None

    def test_owned_rows_need_exactly_one_owner(self, case, kernel):
        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError), transaction.atomic():
            CVELink.objects.create(cve=kernel[0], case=case, url="https://example.com")
        with pytest.raises(IntegrityError), transaction.atomic():
            CVELink.objects.create(url="https://example.com")


# -------------------------------------------------------------------------
# Pages
# -------------------------------------------------------------------------


class TestCasePages:
    def test_create_with_known_and_unknown_ids(self, editor_client, kernel):
        response = editor_client.post(reverse("cves:case-create"), {
            "title": "Linux-kerne, oktober 2026",
            "assessment": "fbdocker01 kører 6.12.113.",
            "solution": "Hold Debian-kernen opdateret.",
            "cve_ids": "cve-2026-93228, CVE-2026-93207\nCVE-2026-100075",
        })
        case = CVECase.objects.get()
        assert response.status_code == 302 and response["Location"] == case.get_absolute_url()
        assert sorted(case.cves.values_list("cve_id", flat=True)) == ["CVE-2026-100075", "CVE-2026-93207", "CVE-2026-93228"]
        new = CVE.objects.get(cve_id="CVE-2026-100075")
        assert new.subject == "Linux-kerne, oktober 2026"
        assert "Oprettet sammen med sagen." in timeline(new)

    def test_create_rejects_bad_ids(self, editor_client):
        response = editor_client.post(reverse("cves:case-create"), {"title": "x", "cve_ids": "CVE-2026-0001 nope"})
        assert response.status_code == 200
        assert "Ikke gyldige CVE-id&#x27;er: nope" in response.content.decode()
        assert not CVECase.objects.exists()

    def test_create_rejects_cves_in_another_case(self, editor_client, case):
        response = editor_client.post(reverse("cves:case-create"), {"title": "x", "cve_ids": "CVE-2026-93228"})
        assert response.status_code == 200
        assert f"Allerede i en anden sag: CVE-2026-93228 (sag #{case.pk})" in response.content.decode()
        assert CVECase.objects.count() == 1

    def test_create_prefills_from_a_cve(self, editor_client, kernel):
        response = editor_client.get(reverse("cves:case-create"), {"cve_ids": "CVE-2026-93228"})
        body = response.content.decode()
        assert "CVE-2026-93228" in body and 'value="svcrdma chunk validation"' in body

    def test_detail_shows_assessment_members_and_outcome_buttons(self, editor_client, case):
        case.assessment = "**Ikke berørt**: ingen NFS-server."
        case.save()
        body = editor_client.get(case.get_absolute_url()).content.decode()
        assert "<strong>Ikke berørt</strong>" in body
        assert "CVE-2026-93228" in body and "CVE-2026-93207" in body
        assert "Færdigbehandlet — ikke berørt" in body and "Færdigbehandlet — risiko accepteret" in body and "Skift status for hele sagen" in body

    def test_state_button(self, editor_client, case, kernel):
        response = editor_client.post(reverse("cves:case-state", args=[case.pk]),
                                      {"state": "solved", "resolution": "not_affected"})
        assert response.status_code == 302
        kernel[1].refresh_from_db()
        assert kernel[1].state == "solved"
        assert editor_client.post(reverse("cves:case-state", args=[case.pk]), {"state": "x"}).status_code == 400

    def test_add_and_remove(self, editor_client, case):
        editor_client.post(reverse("cves:case-add-cves", args=[case.pk]), {"cve_ids": "CVE-2026-98365"})
        assert case.cves.filter(cve_id="CVE-2026-98365").exists()
        cve = CVE.objects.get(cve_id="CVE-2026-93228")
        editor_client.post(reverse("cves:case-remove-cve", args=[case.pk, cve.pk]))
        cve.refresh_from_db()
        assert cve.case is None

    def test_list(self, editor_client, case, kernel):
        """The Sager tab shows each case with every CVE it holds, each a link."""
        body = editor_client.get(reverse("cves:case-list")).content.decode()
        assert f"Sag #{case.pk}" in body
        for cve in kernel:
            assert cve.cve_id in body
            assert f'href="{reverse("cves:detail", args=[cve.pk])}"' in body
        # In cve_id order, under the case
        assert body.index(case.get_absolute_url()) < body.index("CVE-2026-93207") < body.index("CVE-2026-93228")

    def test_case_without_cves_shows_source(self, editor_client, editor):
        CVECase.objects.create(title="CFCS-advarsel", source="CFCS", reference="CERT-1", created_by=editor)
        body = editor_client.get(reverse("cves:case-list")).content.decode()
        assert "CFCS · CERT-1" in body and "Ingen CVE" in body

    def test_tabs_on_both_lists(self, editor_client, case):
        for name, active in (("cves:list", "CVE&#x27;er"), ("cves:case-list", "Sager")):
            response = editor_client.get(reverse(name))
            assert response.context["current_tab"] == ("cves" if name == "cves:list" else "cases")
            body = response.content.decode()
            assert f'href="{reverse("cves:list")}"' in body and f'href="{reverse("cves:case-list")}"' in body
            assert "tab-link-active" in body
        counts = [t["count"] for t in response.context["tabs"]]
        assert counts == ["2 ikke færdigbehandlet · 2 i alt", "1 ikke færdigbehandlet · 1 i alt"]
        CVE.objects.create(cve_id="CVE-2026-7001", subject="x", state=CVE.State.SOLVED)
        counts = [t["count"] for t in editor_client.get(reverse("cves:list")).context["tabs"]]
        assert counts[0] == "2 ikke færdigbehandlet · 3 i alt"  # the total includes færdigbehandlede

    def test_viewer_can_read_but_not_write(self, viewer_client, case):
        assert viewer_client.get(case.get_absolute_url()).status_code == 200
        assert viewer_client.post(reverse("cves:case-state", args=[case.pk]), {"state": "solved"}).status_code == 403
        assert viewer_client.post(reverse("cves:case-create"), {"title": "x"}).status_code == 403
        assert viewer_client.post(reverse("cves:case-add-cves", args=[case.pk]), {"cve_ids": "CVE-2026-0001"}).status_code == 403


class TestCaseDocuments:
    """Links, comments and attachments on a case reuse the CVE views."""

    def test_link_and_comment(self, editor_client, case):
        editor_client.post(case.owner_url("link-create"), {"url": "https://emudhra.we-have-a-problem.com/"},
                           HTTP_HX_REQUEST="true")
        link = CVELink.objects.get()
        assert (link.case, link.cve) == (case, None)
        response = editor_client.post(case.owner_url("comment-create"), {"text": "Testet alle containere."},
                                      HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert case.comments.filter(text="Testet alle containere.").exists()
        assert editor_client.post(case.owner_url("link-delete", link.pk)).status_code == 200
        assert not CVELink.objects.exists()

    def test_attachment_round_trip(self, editor_client, case, cve_files):
        response = editor_client.post(
            case.owner_url("attachment-create"),
            {"file": SimpleUploadedFile("advisory.pdf", PDF, content_type="application/pdf"), "tlp": "amber"},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        a = CVEAttachment.objects.get()
        assert (a.case, a.cve) == (case, None)
        assert a.get_absolute_url() == reverse("cves:case-attachment", args=[case.pk, a.key])
        served = editor_client.get(a.get_absolute_url())
        assert served.status_code == 200 and b"".join(served.streaming_content) == PDF
        # The key alone is not enough: it must belong to this case.
        assert editor_client.get(reverse("cves:attachment", args=[case.cves.first().pk, a.key])).status_code == 404
        assert editor_client.post(a.owner.owner_url("attachment-delete", a.key)).status_code == 200
        assert not CVEAttachment.objects.exists()

    def test_cve_page_documents_still_work(self, editor_client, cve):
        editor_client.post(reverse("cves:link-create", args=[cve.pk]), {"url": "https://example.com"},
                           HTTP_HX_REQUEST="true")
        assert CVELink.objects.get().cve == cve


class TestCVEPageInACase:
    def test_banner_replaces_state_buttons(self, editor_client, case, kernel):
        body = editor_client.get(kernel[0].get_absolute_url()).content.decode()
        assert f"Del af sag #{case.pk}" in body and "Linux-kerne, oktober 2026" in body
        assert "Skift status</span>" not in body

    def test_state_change_on_a_member_cve_is_refused(self, editor_client, case, kernel):
        response = editor_client.post(reverse("cves:state", args=[kernel[0].pk]), {"state": "solved"})
        assert response["Location"] == case.get_absolute_url()
        kernel[0].refresh_from_db()
        assert kernel[0].state == "identified"

    def test_join_an_open_case(self, editor_client, case, cve):
        body = editor_client.get(cve.get_absolute_url()).content.decode()
        assert "Ikke i en sag" in body and "Føj til eksisterende sag" in body and "Ny sag med denne CVE" in body
        editor_client.post(reverse("cves:join-case", args=[cve.pk]), {"case": case.pk})
        cve.refresh_from_db()
        assert cve.case == case
        assert "Ikke i en sag" not in editor_client.get(cve.get_absolute_url()).content.decode()

    def test_join_a_færdigbehandlet_case(self, editor, editor_client, case, cve):
        case.set_state(CVE.State.SOLVED, editor, resolution=CVECase.Resolution.NOT_AFFECTED)
        body = editor_client.get(cve.get_absolute_url()).content.decode()
        assert 'optgroup label="Færdigbehandlede sager"' in body and f'value="{case.pk}"' in body
        editor_client.post(reverse("cves:join-case", args=[cve.pk]), {"case": case.pk})
        cve.refresh_from_db()
        assert (cve.case, cve.state) == (case, CVE.State.SOLVED)  # it takes the case's state

    def test_viewer_sees_the_notice_without_buttons(self, viewer_client, cve):
        body = viewer_client.get(cve.get_absolute_url()).content.decode()
        assert "Ikke i en sag" in body and "Føj til eksisterende sag" not in body and "Ny sag med denne CVE" not in body

    def test_list_flags_cves_without_a_case(self, editor_client, cve):
        body = editor_client.get(reverse("cves:list")).content.decode()
        assert f'{reverse("cves:detail", args=[cve.pk])}#sag' in body and "Ikke i en sag" in body

    def test_list_row_links_to_its_case(self, editor_client, case, kernel, cve):
        body = editor_client.get(reverse("cves:list")).content.decode()
        assert body.count(f'href="{case.get_absolute_url()}"') == 2  # one per member CVE
        assert f"Sag #{case.pk} · {case.title}" in body
        assert body.count("↳ Sag #") == 2  # the free CVE has no case line


# -------------------------------------------------------------------------
# API
# -------------------------------------------------------------------------


def post_case(client, key, body):
    return client.post(reverse("api:cve-case-list"), data=json.dumps(body), content_type="application/json",
                       HTTP_AUTHORIZATION=f"Bearer {key}")


EMUDHRA = {
    "title": "eMudhra CA-kompromittering",
    "assessment": "Produktion er ikke eksponeret.",
    "solution": "Opdatér ca-certificates; byg HedgeDoc og Bitwarden igen.",
    "source_url": "https://harbinger.fynbus.net/cases/1/",
    "comment": "Fra Harbinger.",
    "cves": [
        {"cve_id": "CVE-2026-115557", "subject": "CPython ssl: distrust eMudhra intermediates", "cvss": 9.4},
        {"cve_id": "cve-2026-111943", "subject": "Go crypto/x509: distrust eMudhra intermediates"},
    ],
}


class TestCaseAPI:
    def test_create(self, client, write_key):
        response = post_case(client, write_key, EMUDHRA)
        assert response.status_code == 201
        data = response.json()
        assert data["created"] is True and data["title"] == "eMudhra CA-kompromittering"
        assert [c["cve_id"] for c in data["cves"]] == ["CVE-2026-111943", "CVE-2026-115557"]
        case = CVECase.objects.get()
        assert (case.source, case.assessment) == ("harbinger", "Produktion er ikke eksponeret.")
        assert case.comments.filter(text="Fra Harbinger.").exists()
        assert CVE.objects.get(cve_id="CVE-2026-115557").source == "api"  # no per-CVE source_url given

    def test_create_solved_puts_members_in_solved(self, client, write_key):
        response = post_case(client, write_key, {**EMUDHRA, "state": "solved", "resolution": "not_affected"})
        assert response.json()["outcome"] == "Færdigbehandlet — ikke berørt"
        assert set(CVE.objects.values_list("state", flat=True)) == {"solved"}

    def test_create_with_risk_accepted(self, client, write_key):
        response = post_case(client, write_key, {**EMUDHRA, "state": "solved", "resolution": "risk_accepted"})
        assert response.status_code == 201
        assert response.json()["outcome"] == "Færdigbehandlet — risiko accepteret"

    def test_extend_existing_case_by_id(self, client, write_key):
        case_id = post_case(client, write_key, EMUDHRA).json()["id"]
        response = post_case(client, write_key, {
            "id": case_id, "solution": "Nyt.",
            "cves": [{"cve_id": "CVE-2026-115557", "subject": "x"}, {"cve_id": "CVE-2026-120000", "subject": "Node"}],
        })
        assert response.status_code == 200 and response.json()["created"] is False
        case = CVECase.objects.get()
        assert case.cves.count() == 3
        assert (case.title, case.assessment, case.solution) == ("eMudhra CA-kompromittering", "Produktion er ikke eksponeret.", "Nyt.")
        assert CVE.objects.get(cve_id="CVE-2026-115557").subject.startswith("CPython")  # existing fields kept

    def test_existing_free_cve_joins(self, client, write_key, cve):
        post_case(client, write_key, {"title": "t", "cves": [{"cve_id": cve.cve_id, "subject": "ignored"}]})
        cve.refresh_from_db()
        assert cve.case is not None and cve.subject == "OpenSSH regreSSHion igen"

    def test_conflict_changes_nothing(self, client, write_key, case):
        response = post_case(client, write_key, {
            "title": "Andet", "cves": [{"cve_id": "CVE-2026-93228", "subject": "x"}, {"cve_id": "CVE-2026-0005", "subject": "y"}],
        })
        assert response.status_code == 409
        assert response.json()["cves"] == [{"cve_id": "CVE-2026-93228", "case_id": case.pk, "case_title": case.title}]
        assert CVECase.objects.count() == 1 and not CVE.objects.filter(cve_id="CVE-2026-0005").exists()

    @pytest.mark.parametrize("body, field", [
        ({"cves": []}, "title"),
        ({"title": "t", "cves": "CVE-1"}, "cves"),
        ({"title": "t", "cves": [{"cve_id": "nope", "subject": "x"}]}, "cves[0].cve_id"),
        ({"title": "t", "cves": [{"cve_id": "CVE-2026-0001"}]}, "cves[0].subject"),
        ({"title": "t", "state": "done"}, "state"),
        ({"title": "t", "resolution": "patched"}, "resolution"),
        ({"title": "t", "id": "1"}, "id"),
        ({"title": "t", "source_url": "ftp://x"}, "source_url"),
    ])
    def test_validation(self, client, write_key, body, field):
        response = post_case(client, write_key, body)
        assert response.status_code == 400 and response.json()["field"] == field
        assert not CVECase.objects.exists()

    def test_unknown_id_is_404(self, client, write_key):
        assert post_case(client, write_key, {"id": 999, "cves": []}).status_code == 404

    def test_read_key_cannot_write_and_can_read(self, client, read_key, case):
        assert post_case(client, read_key, EMUDHRA).status_code == 403
        listed = client.get(reverse("api:cve-case-list"), HTTP_AUTHORIZATION=f"Bearer {read_key}").json()["cases"]
        assert [c["id"] for c in listed] == [case.pk]
        one = client.get(reverse("api:cve-case-detail", args=[case.pk]), HTTP_AUTHORIZATION=f"Bearer {read_key}")
        assert one.json()["cves"][0]["cve_id"] == "CVE-2026-93207"

    def test_cve_payload_names_its_case(self, client, read_key, case):
        data = client.get(reverse("api:cve-detail", args=["CVE-2026-93228"]), HTTP_AUTHORIZATION=f"Bearer {read_key}").json()
        assert data["case"] == {"id": case.pk, "title": case.title}


class TestSourceAndReference:
    """Warnings without a CVE number (e.g. from CFCS) become cases with no CVEs."""

    def test_create_without_cves(self, editor_client):
        response = editor_client.post(reverse("cves:case-create"), {
            "title": "CFCS: phishing mod trafikselskaber", "source": "CFCS",
            "reference": "CFCS-advarsel 2026-10-24", "source_url": "https://www.cfcs.dk/",
            "assessment": "Ingen tegn hos os.", "solution": "", "cve_ids": "",
        })
        case = CVECase.objects.get()
        assert response.status_code == 302
        assert (case.source, case.reference, case.cves.count()) == ("CFCS", "CFCS-advarsel 2026-10-24", 0)
        body = editor_client.get(case.get_absolute_url()).content.decode()
        assert "via CFCS" in body
        assert "CFCS-advarsel 2026-10-24" in body
        assert "Ingen CVE" in body
        assert "CFCS ↗" in body

    def test_harbinger_source_reads_as_a_name(self, case):
        case.source = "harbinger"
        assert case.source_label == "Harbinger"

    def test_case_list_search(self, editor_client, case, editor):
        cfcs = CVECase.objects.create(title="CFCS-advarsel", source="CFCS", reference="2026-10-24", created_by=editor)
        assert list(editor_client.get(reverse("cves:case-list"), {"q": "2026-10-24"}).context["cases"]) == [cfcs]
        assert list(editor_client.get(reverse("cves:case-list"), {"q": "93228"}).context["cases"]) == [case]

    def test_api_takes_source_and_reference(self, client, write_key):
        response = post_case(client, write_key, {"title": "CFCS-advarsel", "source": "CFCS",
                                                 "reference": "CFCS 2026-10-24", "cves": []})
        assert response.status_code == 201
        data = response.json()
        assert (data["source"], data["reference"], data["cves"]) == ("CFCS", "CFCS 2026-10-24", [])
        again = post_case(client, write_key, {"id": data["id"], "reference": "CFCS 2026-10-25"})
        assert again.json()["reference"] == "CFCS 2026-10-25"
