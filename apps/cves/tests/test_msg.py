"""Outlook .msg attachments: parsing, upload, PDFs unpacked from the mail, preview, download."""

import io
from datetime import datetime, timezone

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.cves import msg
from apps.cves.models import CVEAttachment

from .msgfactory import build_msg

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"
SENT = datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc)


def fe_csirt_mail(**overrides) -> bytes:
    kwargs = dict(
        subject="TLP:AMBER FE-CSIRT advarsel 2026-0142: PHP OOM (CVE-2026-109618)",
        sender_name="FE-CSIRT", sender_email="CSIRT@fe-ddis.dk", to="IT-sikkerhed",
        body="Kære modtager,\n\nOpdatér PHP til 8.3.36.\n<script>alert('x')</script>\n",
        sent=SENT,
        attachments=[("advisory-2026-0142.pdf", PDF * 120, "application/pdf"), ("logo.png", b"\x89PNG\r\n", "image/png")],
    )
    kwargs.update(overrides)
    return build_msg(**kwargs)


@pytest.fixture
def editor_client(editor):
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


def upload(client, cve, data, name="advarsel.msg", **fields):
    return client.post(
        reverse("cves:attachment-create", args=[cve.pk]),
        {"file": SimpleUploadedFile(name, data, content_type="application/vnd.ms-outlook"), **fields},
        HTTP_HX_REQUEST="true",
    )


class TestParser:
    def test_reads_headers_body_and_attachments(self):
        info = msg.parse(io.BytesIO(fe_csirt_mail()))
        assert info.subject.startswith("TLP:AMBER FE-CSIRT")
        assert info.sender == "FE-CSIRT <CSIRT@fe-ddis.dk>"
        assert (info.to, info.sent) == ("IT-sikkerhed", SENT)
        assert "Opdatér PHP til 8.3.36." in info.body
        assert [(a.filename, a.is_pdf) for a in info.attachments] == [("advisory-2026-0142.pdf", True), ("logo.png", False)]

    def test_html_only_body_becomes_text_without_scripts(self):
        info = msg.parse(io.BytesIO(build_msg(subject="x", html_body="<html><head><style>p{color:red}</style></head>"
                                              "<body><p>Hej <b>der</b></p><script>steal()</script><p>Linje&nbsp;2</p></body></html>")))
        assert "Hej der" in info.body and "Linje" in info.body
        assert "steal" not in info.body and "color" not in info.body

    def test_rejects_non_ole_and_ole_without_mapi(self):
        with pytest.raises(msg.MsgError):
            msg.parse(io.BytesIO(PDF))
        with pytest.raises(msg.MsgError):
            msg.parse(io.BytesIO(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600))

    @pytest.mark.parametrize("text,expected", [
        ("TLP:AMBER advarsel", "amber"), ("[TLP: RED]", "red"), ("tlp:green", "green"),
        ("TLP:AMBER+STRICT", "amber_strict"), ("TLP:WHITE", "clear"), ("TLP:CLEAR", "clear"), ("ingen markering", ""),
    ])
    def test_detect_tlp(self, text, expected):
        assert msg.detect_tlp(text) == expected


class TestUpload:
    def test_mail_with_pdf_is_stored_and_pdf_unpacked(self, editor_client, cve, cve_files):
        response = upload(editor_client, cve, fe_csirt_mail())
        assert response.status_code == 200
        mail = CVEAttachment.objects.get(kind="msg")
        assert mail.email_subject.startswith("TLP:AMBER FE-CSIRT")
        assert (mail.email_from, mail.email_to, mail.email_sent) == ("FE-CSIRT <CSIRT@fe-ddis.dk>", "IT-sikkerhed", SENT)
        assert mail.tlp == "amber"  # detected from the subject, none chosen
        assert mail.source == "FE-CSIRT <CSIRT@fe-ddis.dk>"
        assert mail.file.name.endswith(".msg") and (cve_files / mail.file.name).exists()
        (pdf,) = CVEAttachment.objects.filter(kind="pdf")  # the PNG is not unpacked
        assert (pdf.parent, pdf.tlp, pdf.title, pdf.size) == (mail, "amber", "advisory-2026-0142.pdf", len(PDF * 120))
        assert (cve_files / pdf.file.name).read_bytes() == PDF * 120
        body = response.content.decode()
        assert f"cve-attachment-{mail.key}" in body and f"cve-attachment-{pdf.key}" in body
        assert "Pakket ud af mailen" in body

    def test_chosen_tlp_and_source_win(self, editor_client, cve):
        upload(editor_client, cve, fe_csirt_mail(), tlp="red", source="FE-CSIRT")
        mail = CVEAttachment.objects.get(kind="msg")
        assert (mail.tlp, mail.source) == ("red", "FE-CSIRT")
        assert CVEAttachment.objects.get(kind="pdf").tlp == "red"

    def test_fake_msg_is_rejected(self, editor_client, cve):
        response = upload(editor_client, cve, PDF, name="advarsel.msg")
        assert "ikke en Outlook-mail" in response.content.decode()
        response = upload(editor_client, cve, b"Inno Setup Messages (6.5.0)", name="setup.msg")
        assert "ikke en Outlook-mail" in response.content.decode()
        assert not CVEAttachment.objects.exists()

    def test_viewer_cannot_upload(self, viewer_client, cve):
        assert upload(viewer_client, cve, fe_csirt_mail()).status_code in (302, 403)
        assert not CVEAttachment.objects.exists()


class TestPreviewAndDownload:
    def test_preview_escapes_mail_text_and_is_framable(self, editor_client, viewer_client, cve):
        upload(editor_client, cve, fe_csirt_mail())
        mail = CVEAttachment.objects.get(kind="msg")
        response = viewer_client.get(reverse("cves:attachment-preview", args=[cve.pk, mail.key]))
        assert response.status_code == 200
        assert response["X-Frame-Options"] == "SAMEORIGIN"
        assert "no-store" in response["Cache-Control"]
        body = response.content.decode()
        assert "FE-CSIRT &lt;CSIRT@fe-ddis.dk&gt;" in body
        assert "Opdatér PHP til 8.3.36." in body
        assert "<script>alert" not in body and "&lt;script&gt;alert" in body
        assert "advisory-2026-0142.pdf" in body  # link to the unpacked PDF

    def test_msg_is_always_a_download(self, editor_client, cve):
        raw = fe_csirt_mail()
        upload(editor_client, cve, raw)
        mail = CVEAttachment.objects.get(kind="msg")
        response = editor_client.get(reverse("cves:attachment", args=[cve.pk, mail.key]))
        assert response["Content-Type"] == "application/vnd.ms-outlook"
        assert response["Content-Disposition"].startswith("attachment")
        assert b"".join(response.streaming_content) == raw

    def test_preview_only_for_mails(self, editor_client, cve):
        upload(editor_client, cve, fe_csirt_mail())
        pdf = CVEAttachment.objects.get(kind="pdf")
        assert editor_client.get(reverse("cves:attachment-preview", args=[cve.pk, pdf.key])).status_code == 404

    def test_row_opens_preview_and_downloads_original(self, editor_client, cve):
        upload(editor_client, cve, fe_csirt_mail())
        mail = CVEAttachment.objects.get(kind="msg")
        page = editor_client.get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert f"/cves/{cve.pk}/attachments/{mail.key}/preview/" in page
        assert f"/cves/{cve.pk}/attachments/{mail.key}/?download=1" in page


class TestDelete:
    def test_deleting_the_mail_keeps_unpacked_pdfs(self, editor_client, cve, cve_files):
        upload(editor_client, cve, fe_csirt_mail())
        mail = CVEAttachment.objects.get(kind="msg")
        pdf = CVEAttachment.objects.get(kind="pdf")
        mail_path = cve_files / mail.file.name
        editor_client.post(reverse("cves:attachment-delete", args=[cve.pk, mail.key]))
        assert not mail_path.exists()
        pdf.refresh_from_db()
        assert pdf.parent is None
        assert (cve_files / pdf.file.name).exists()
