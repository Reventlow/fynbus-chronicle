"""PDF attachments on a CVE: upload, validation, TLP, serving, deletion, permissions."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cves.models import CVEAttachment

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


@pytest.fixture
def editor_client(editor):
    """Own session: conftest's editor_client and viewer_client share one Client."""
    from django.test import Client

    c = Client()
    c.force_login(editor)
    return c


@pytest.fixture
def viewer_client(viewer):
    from django.test import Client

    c = Client()
    c.force_login(viewer)
    return c


@pytest.fixture(autouse=True)
def cve_files(settings, tmp_path):
    settings.CVE_FILES_DIR = tmp_path / "cve_files"
    return settings.CVE_FILES_DIR


def upload(client, cve, name="FE-CSIRT-2026-0142.pdf", data=PDF, **fields):
    return client.post(
        reverse("cves:attachment-create", args=[cve.pk]),
        {"file": SimpleUploadedFile(name, data, content_type="application/pdf"), **fields},
        HTTP_HX_REQUEST="true",
    )


class TestUpload:
    def test_editor_uploads_pdf_with_tlp_and_source(self, editor_client, cve, cve_files):
        response = upload(editor_client, cve, title="FE-CSIRT advisory 2026-0142", source="FE-CSIRT", tlp="amber")
        assert response.status_code == 200
        a = CVEAttachment.objects.get(cve=cve)
        assert (a.title, a.source, a.tlp, a.original_name, a.size) == (
            "FE-CSIRT advisory 2026-0142", "FE-CSIRT", "amber", "FE-CSIRT-2026-0142.pdf", len(PDF))
        assert (cve_files / a.file.name).read_bytes() == PDF
        assert a.key in a.file.name and "FE-CSIRT" not in a.file.name  # stored under the random key
        body = response.content.decode()
        assert "TLP:AMBER" in body and "open-pdf" in body
        assert 'hx-swap-oob="delete"' in body  # removes the "no PDFs yet" placeholder

    def test_rejects_non_pdf_content_even_with_pdf_name(self, editor_client, cve):
        response = upload(editor_client, cve, name="evil.pdf", data=b"MZ\x90\x00 not a pdf")
        assert response["HX-Retarget"] == "#cve-attachment-form-container"
        assert "ikke en gyldig PDF" in response.content.decode()
        assert not CVEAttachment.objects.exists()

    def test_rejects_other_extensions_and_oversize(self, editor_client, cve, settings):
        assert "Kun PDF" in upload(editor_client, cve, name="advisory.docx").content.decode()
        settings.CVE_ATTACHMENT_MAX_BYTES = 10
        assert "for stor" in upload(editor_client, cve).content.decode()
        assert not CVEAttachment.objects.exists()

    def test_viewer_cannot_upload_or_delete(self, viewer_client, editor_client, cve):
        assert upload(viewer_client, cve).status_code in (302, 403)
        assert not CVEAttachment.objects.exists()
        upload(editor_client, cve)
        a = CVEAttachment.objects.get()
        viewer_client.post(reverse("cves:attachment-delete", args=[cve.pk, a.key]))
        assert CVEAttachment.objects.filter(pk=a.pk).exists()

    def test_upload_touches_cve(self, editor_client, cve):
        before = cve.updated_at
        upload(editor_client, cve)
        cve.refresh_from_db()
        assert cve.updated_at > before


class TestServe:
    def test_inline_for_lightbox_and_download(self, editor_client, viewer_client, cve):
        upload(editor_client, cve)
        a = CVEAttachment.objects.get()
        url = reverse("cves:attachment", args=[cve.pk, a.key])
        response = viewer_client.get(url)  # viewers may read
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response["Content-Disposition"].startswith("inline")
        assert response["X-Frame-Options"] == "SAMEORIGIN"  # framable by our own lightbox only
        assert "no-store" in response["Cache-Control"]
        assert b"".join(response.streaming_content) == PDF
        assert viewer_client.get(url + "?download=1")["Content-Disposition"].startswith("attachment")

    def test_requires_login_and_matching_cve(self, client, editor_client, cve, editor):
        upload(editor_client, cve)
        a = CVEAttachment.objects.get()
        anon = client.__class__()
        assert anon.get(reverse("cves:attachment", args=[cve.pk, a.key])).status_code == 302
        assert editor_client.get(reverse("cves:attachment", args=[cve.pk + 999, a.key])).status_code == 404

    def test_other_pages_still_deny_framing(self, editor_client, cve):
        assert editor_client.get(reverse("cves:detail", args=[cve.pk]))["X-Frame-Options"] == "DENY"


class TestDeleteAndPage:
    def test_delete_removes_row_and_file(self, editor_client, cve, cve_files):
        upload(editor_client, cve)
        a = CVEAttachment.objects.get()
        path = cve_files / a.file.name
        assert path.exists()
        response = editor_client.post(reverse("cves:attachment-delete", args=[cve.pk, a.key]))
        assert response.status_code == 200
        assert not CVEAttachment.objects.exists()
        assert not path.exists()

    def test_detail_shows_section_lightbox_and_form(self, editor_client, cve):
        upload(editor_client, cve, title="Advisory", tlp="red")
        body = editor_client.get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert "Vedhæftninger" in body and "Advisory" in body and "TLP:RED" in body
        assert "open-pdf.window" in body  # the lightbox listener
        assert 'hx-encoding="multipart/form-data"' in body

    def test_viewer_sees_list_but_no_upload_form(self, viewer_client, editor_client, cve):
        upload(editor_client, cve, title="Advisory")
        body = viewer_client.get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert "Advisory" in body
        assert "Vedhæft</button>" not in body


def make_odt(mimetype=b"application/vnd.oasis.opendocument.text") -> bytes:
    """A minimal OpenDocument text: ``mimetype`` first and stored, as the spec says."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), mimetype, compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", "<office:document-content/>", compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


class TestOdt:
    def test_editor_uploads_odt(self, editor_client, cve, cve_files):
        data = make_odt()
        response = upload(editor_client, cve, name="CFCS-orientering.odt", data=data, tlp="green")
        assert response.status_code == 200
        a = CVEAttachment.objects.get(cve=cve)
        assert (a.kind, a.tlp, a.original_name, a.size) == ("odt", "green", "CFCS-orientering.odt", len(data))
        assert a.file.name.endswith(f"{a.key}.odt")
        body = response.content.decode()
        assert "ODT-dokument" in body and a.get_download_url() in body
        assert "open-pdf" not in body  # no lightbox: a browser can't show an .odt

    def test_rejects_fake_and_other_opendocument_types(self, editor_client, cve):
        for data in (b"PK\x03\x04 not really a zip", PDF, make_odt(b"application/vnd.oasis.opendocument.spreadsheet")):
            response = upload(editor_client, cve, name="orientering.odt", data=data)
            assert "ikke et gyldigt ODT-dokument" in response.content.decode()
        assert not CVEAttachment.objects.exists()

    def test_always_served_as_download(self, editor_client, viewer_client, cve):
        upload(editor_client, cve, name="orientering.odt", data=make_odt())
        a = CVEAttachment.objects.get()
        response = viewer_client.get(reverse("cves:attachment", args=[cve.pk, a.key]))
        assert response["Content-Type"] == "application/vnd.oasis.opendocument.text"
        assert response["Content-Disposition"].startswith("attachment")
        assert "orientering.odt" in response["Content-Disposition"]
        assert "no-store" in response["Cache-Control"]

    def test_case_accepts_odt(self, editor_client, cve_files):
        from apps.cves.models import CVECase

        case = CVECase.objects.create(title="Orientering: kendte IOC'er")
        response = editor_client.post(
            reverse("cves:case-attachment-create", args=[case.pk]),
            {"file": SimpleUploadedFile("ioc.odt", make_odt(), content_type="application/vnd.oasis.opendocument.text")},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert case.attachments.get().is_odt
