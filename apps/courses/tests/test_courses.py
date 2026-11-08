"""Kursusmateriale (1.20.0): folders of course videos, presentations, PDFs
and links. Anyone can view without logging in; only editors can change anything."""

import io
import os
import zipfile

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.courses.models import CourseFolder, CourseMaterial

pytestmark = pytest.mark.django_db

MP4 = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
PDF = b"%PDF-1.7\n" + b"x" * 500


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


PPTX = _zip({"[Content_Types].xml": b"<Types/>", "ppt/presentation.xml": b"<p/>"})
ODP = _zip({"mimetype": b"application/vnd.oasis.opendocument.presentation", "content.xml": b"<x/>"})
PPT = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600


@pytest.fixture(autouse=True)
def files_dir(settings, tmp_path):
    settings.COURSE_FILES_DIR = tmp_path / "course_files"
    # No LibreOffice unless a test installs the fake one below.
    settings.COURSE_SOFFICE = str(tmp_path / "no-soffice-here")
    return settings.COURSE_FILES_DIR


def fake_soffice(settings, tmp_path, body: str):
    """Install a stand-in for LibreOffice: a shell script whose body gets
    the output directory as $OUT (the --outdir argument)."""
    script = tmp_path / "soffice"
    script.write_text(
        "#!/bin/sh\n"
        'while [ $# -gt 0 ]; do [ "$1" = --outdir ] && OUT="$2"; shift; done\n'
        'mkdir -p "$OUT"\n' + body + "\n"
    )
    script.chmod(0o755)
    settings.COURSE_SOFFICE = str(script)


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x", first_name="Gorm", last_name="Reventlow")
    client.force_login(user)
    return user


@pytest.fixture
def viewer(client):
    user = User.objects.create_user("viewer", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(user)
    return user


@pytest.fixture
def folder(db):
    return CourseFolder.objects.create(name="Anthropic", description="Claude-kurser")


def upload(client, folder, name, data, **extra):
    return client.post(
        reverse("courses:material-add", args=[folder.slug]),
        {"file": SimpleUploadedFile(name, data), "title": "", "description": "", "url": "", **extra},
    )


# --- folders -------------------------------------------------------------------


def test_pages_are_public_and_noindex(client, folder):
    CourseMaterial.objects.create(folder=folder, kind="link", title="Academy", url="https://example.test")
    for url in (reverse("courses:index"), folder.get_absolute_url()):
        resp = client.get(url)
        assert resp.status_code == 200 and resp["X-Robots-Tag"] == "noindex, nofollow"
        html = resp.content.decode()
        assert "Anthropic" in html and "Log ind" in html and "Ny mappe" not in html and "Tilføj materiale" not in html


def test_anonymous_cannot_change_anything(client, folder):
    m = CourseMaterial.objects.create(folder=folder, kind="link", title="Academy", url="https://example.test")
    assert client.post(reverse("courses:index"), {"name": "X"}).status_code == 403
    for url, data in (
        (reverse("courses:material-add", args=[folder.slug]), {"url": "https://x.test", "title": "x"}),
        (reverse("courses:material-edit", args=[m.key]), {"title": "y", "folder": folder.pk}),
        (reverse("courses:material-delete", args=[m.key]), {}),
        (reverse("courses:folder-edit", args=[folder.slug]), {"name": "y"}),
        (reverse("courses:folder-delete", args=[folder.slug]), {}),
    ):
        resp = client.post(url, data)
        assert resp.status_code == 302 and "/login" in resp["Location"]
    assert CourseMaterial.objects.get().title == "Academy" and CourseFolder.objects.get().name == "Anthropic"


def test_uploader_name_hidden_from_anonymous(client, editor, folder):
    upload(client, folder, "Guide.pdf", PDF)
    assert "af Gorm Reventlow" in client.get(folder.get_absolute_url()).content.decode()
    client.logout()
    assert "Gorm Reventlow" not in client.get(folder.get_absolute_url()).content.decode()


def test_create_folder_with_ascii_slug(client, editor):
    resp = client.post(reverse("courses:index"), {"name": "Grøn IT på Åen", "description": "x"})
    f = CourseFolder.objects.get()
    assert f.slug == "groen-it-paa-aaen" and f.created_by == editor
    assert resp.status_code == 302 and resp["Location"] == f.get_absolute_url()


def test_duplicate_folder_name_is_refused(client, editor, folder):
    resp = client.post(reverse("courses:index"), {"name": "Anthropic"})
    assert resp.status_code == 200 and CourseFolder.objects.count() == 1


def test_index_lists_folders_with_counts(client, editor, folder):
    upload(client, folder, "intro.mp4", MP4)
    client.post(reverse("courses:material-add", args=[folder.slug]), {"url": "https://anthropic.com/learn", "title": "Learn"})
    html = client.get(reverse("courses:index")).content.decode()
    assert "Anthropic" in html and "1 video" in html and "1 link" in html and "Ny mappe" in html


def test_index_sorts_folders_by_name(client, editor, folder):
    CourseFolder.objects.create(name="microsoft 365")
    CourseFolder.objects.create(name="Cisco")
    html = client.get(reverse("courses:index")).content.decode()
    assert html.index("Anthropic") < html.index("Cisco") < html.index("microsoft 365")


def test_reserved_slug_is_avoided(client, editor):
    client.post(reverse("courses:index"), {"name": "Fil"})
    assert CourseFolder.objects.get().slug == "fil-2"


def test_rename_folder_updates_slug(client, editor, folder):
    resp = client.post(reverse("courses:folder-edit", args=[folder.slug]), {"name": "Anthropic Academy", "description": ""})
    folder.refresh_from_db()
    assert folder.slug == "anthropic-academy" and resp["Location"] == folder.get_absolute_url()


def test_delete_folder_removes_files(client, editor, folder, files_dir):
    upload(client, folder, "intro.mp4", MP4)
    path = CourseMaterial.objects.get().file.path
    client.post(reverse("courses:folder-delete", args=[folder.slug]))
    assert not CourseFolder.objects.exists() and not CourseMaterial.objects.exists()
    assert not os.path.exists(path)


# --- uploads -------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,data,kind",
    [
        ("Intro.mp4", MP4, "video"),
        ("clip.webm", WEBM, "video"),
        ("clip.MOV", MP4, "video"),
        ("Slides.pptx", PPTX, "slides"),
        ("Slides.odp", ODP, "slides"),
        ("old.ppt", PPT, "slides"),
        ("Guide.pdf", PDF, "pdf"),
    ],
)
def test_upload_detects_kind(client, editor, folder, name, data, kind):
    resp = upload(client, folder, name, data)
    assert resp.status_code == 302
    m = CourseMaterial.objects.get()
    assert m.kind == kind and m.original_name == name and m.size == len(data)
    assert m.title == name.rsplit(".", 1)[0] and m.added_by == editor
    assert m.file.name.startswith(f"{m.key[:2]}/{m.key}")


@pytest.mark.parametrize(
    "name,data,error",
    [
        ("evil.exe", b"MZ" + b"\x00" * 100, "Filtypen kan ikke lægges op"),
        ("fake.pdf", b"MZ" + b"\x00" * 100, "ligner ikke en PDF"),
        ("fake.pptx", _zip({"word/document.xml": b"x"}), "ligner ikke en PPTX"),
        ("fake.mp4", b"hello world, not a video", "ligner ikke en MP4"),
        ("empty.pdf", b"", "tom"),
    ],
)
def test_upload_rejects_bad_files(client, editor, folder, name, data, error):
    resp = client.post(
        reverse("courses:material-add", args=[folder.slug]),
        {"file": SimpleUploadedFile(name, data)},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200 and error in resp.content.decode()
    assert not CourseMaterial.objects.exists()


def test_upload_size_limit(client, editor, folder, settings):
    settings.COURSE_FILE_MAX_BYTES = 100
    resp = client.post(
        reverse("courses:material-add", args=[folder.slug]),
        {"file": SimpleUploadedFile("big.pdf", PDF)},
        HTTP_HX_REQUEST="true",
    )
    assert "større end" in resp.content.decode() and not CourseMaterial.objects.exists()


def test_htmx_upload_redirects(client, editor, folder):
    resp = client.post(
        reverse("courses:material-add", args=[folder.slug]),
        {"file": SimpleUploadedFile("a.pdf", PDF), "title": "Kursusbevis"},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 204 and resp["HX-Redirect"] == folder.get_absolute_url()
    assert CourseMaterial.objects.get().title == "Kursusbevis"


def test_add_link(client, editor, folder):
    client.post(reverse("courses:material-add", args=[folder.slug]), {"url": "anthropic.com/learn", "title": "Anthropic Academy"})
    m = CourseMaterial.objects.get()
    assert m.kind == "link" and m.url == "https://anthropic.com/learn" and not m.file


def test_link_needs_title_and_not_both(client, editor, folder):
    url = reverse("courses:material-add", args=[folder.slug])
    resp = client.post(url, {"url": "https://example.test"}, HTTP_HX_REQUEST="true")
    assert "Giv linket en titel" in resp.content.decode()
    resp = client.post(url, {"url": "https://example.test", "title": "x", "file": SimpleUploadedFile("a.pdf", PDF)}, HTTP_HX_REQUEST="true")
    assert "ikke flere" in resp.content.decode()
    resp = client.post(url, {}, HTTP_HX_REQUEST="true")
    assert "Vælg en fil eller skriv et link" in resp.content.decode()
    assert not CourseMaterial.objects.exists()


def test_javascript_link_is_refused(client, editor, folder):
    client.post(reverse("courses:material-add", args=[folder.slug]), {"url": "javascript:alert(1)", "title": "x"})
    assert not CourseMaterial.objects.exists()


# --- serving -------------------------------------------------------------------


def test_video_streams_inline_with_ranges(client, editor, folder):
    upload(client, folder, "Intro æ.mp4", MP4)
    m = CourseMaterial.objects.get()
    resp = client.get(m.get_file_url())
    assert resp.status_code == 200 and resp["Content-Type"] == "video/mp4" and resp["Accept-Ranges"] == "bytes"
    assert resp["Content-Disposition"].startswith("inline") and b"".join(resp.streaming_content) == MP4
    resp = client.get(m.get_file_url(), HTTP_RANGE="bytes=100-199")
    assert resp.status_code == 206 and resp["Content-Range"] == f"bytes 100-199/{len(MP4)}"
    assert b"".join(resp.streaming_content) == MP4[100:200]
    resp = client.get(m.get_download_url())
    assert resp["Content-Disposition"].startswith("attachment") and "filename*=utf-8''Intro%20%C3%A6.mp4" in resp["Content-Disposition"]


def test_presentation_always_downloads_and_pdf_opens_inline(client, editor, folder):
    upload(client, folder, "Slides.pptx", PPTX)
    upload(client, folder, "Guide.pdf", PDF)
    pptx, pdf = CourseMaterial.objects.order_by("pk")
    resp = client.get(pptx.get_file_url())
    assert resp["Content-Disposition"].startswith("attachment")
    assert resp["Content-Type"].startswith("application/vnd.openxmlformats-officedocument.presentationml")
    resp = client.get(pdf.get_file_url())
    assert resp["Content-Disposition"].startswith("inline") and resp["Content-Type"] == "application/pdf"
    assert resp["X-Content-Type-Options"] == "nosniff"


def test_file_is_public(client, editor, folder):
    upload(client, folder, "Guide.pdf", PDF)
    m = CourseMaterial.objects.get()
    client.logout()
    resp = client.get(m.get_file_url())
    assert resp.status_code == 200 and b"".join(resp.streaming_content) == PDF


def test_link_has_no_file_url(client, editor, folder):
    m = CourseMaterial.objects.create(folder=folder, kind="link", title="x", url="https://example.test")
    assert client.get(m.get_file_url()).status_code == 404


# --- folder page, edit and delete ----------------------------------------------


def test_folder_page_groups_by_kind(client, editor, folder):
    upload(client, folder, "Intro.mp4", MP4)
    upload(client, folder, "Guide.pdf", PDF)
    client.post(reverse("courses:material-add", args=[folder.slug]), {"url": "https://example.test", "title": "Academy"})
    html = client.get(folder.get_absolute_url()).content.decode()
    assert html.index("Videoer") < html.index("PDF&#x27;er") < html.index("Links")
    assert "Præsentationer" not in html
    assert "Afspil" in html and "Tilføj materiale" in html and "Rediger mappe" in html


def test_edit_and_move_material(client, editor, folder):
    other = CourseFolder.objects.create(name="Microsoft")
    upload(client, folder, "Guide.pdf", PDF)
    m = CourseMaterial.objects.get()
    resp = client.post(reverse("courses:material-edit", args=[m.key]), {"title": "Ny titel", "description": "d", "folder": other.pk})
    m.refresh_from_db()
    assert m.title == "Ny titel" and m.folder == other and resp["Location"] == other.get_absolute_url()


def test_edit_link_url(client, editor, folder):
    m = CourseMaterial.objects.create(folder=folder, kind="link", title="x", url="https://old.test")
    client.post(reverse("courses:material-edit", args=[m.key]), {"title": "x", "url": "new.test/a", "folder": folder.pk})
    m.refresh_from_db()
    assert m.url == "https://new.test/a"
    client.post(reverse("courses:material-edit", args=[m.key]), {"title": "x", "url": "", "folder": folder.pk})
    m.refresh_from_db()
    assert m.url == "https://new.test/a"


def test_delete_material_removes_file(client, editor, folder, files_dir):
    upload(client, folder, "Guide.pdf", PDF)
    m = CourseMaterial.objects.get()
    path = m.file.path
    client.post(reverse("courses:material-delete", args=[m.key]))
    assert not CourseMaterial.objects.exists() and not os.path.exists(path)


def test_viewer_can_view_but_not_change(client, viewer, folder):
    m = CourseMaterial.objects.create(folder=folder, kind="link", title="Academy", url="https://example.test")
    html = client.get(folder.get_absolute_url()).content.decode()
    assert "Academy" in html and "Tilføj materiale" not in html and "Rediger mappe" not in html
    assert "Ny mappe" not in client.get(reverse("courses:index")).content.decode()
    assert client.post(reverse("courses:index"), {"name": "X"}).status_code == 403
    assert client.post(reverse("courses:material-add", args=[folder.slug]), {"url": "https://x.test", "title": "x"}).status_code == 403
    assert client.post(reverse("courses:material-delete", args=[m.key])).status_code == 403
    assert client.post(reverse("courses:material-edit", args=[m.key]), {"title": "y", "folder": folder.pk}).status_code == 403
    assert client.post(reverse("courses:folder-edit", args=[folder.slug]), {"name": "y"}).status_code == 403
    assert client.post(reverse("courses:folder-delete", args=[folder.slug])).status_code == 403
    assert CourseMaterial.objects.count() == 1 and CourseFolder.objects.get().name == "Anthropic"


def test_titles_are_escaped(client, editor, folder):
    CourseMaterial.objects.create(folder=folder, kind="link", title="<script>x</script>", url="https://example.test")
    html = client.get(folder.get_absolute_url()).content.decode()
    assert "<script>x</script>" not in html and "&lt;script&gt;x&lt;/script&gt;" in html


def test_nav_links_to_courses(client, editor):
    html = client.get(reverse("courses:index")).content.decode()
    assert 'href="/kursus/"' in html and "Kursusmateriale" in html


# --- slide conversion (1.20.1) ---------------------------------------------------


def test_presentation_is_converted_at_upload(client, editor, folder, settings, tmp_path):
    fake_soffice(settings, tmp_path, 'printf "%%PDF-1.4 fake" > "$OUT/slides.pdf"')
    upload(client, folder, "Workshop.pptx", PPTX)
    m = CourseMaterial.objects.get()
    assert m.preview and m.preview.name.endswith(".preview.pdf") and m.preview_error == ""
    assert m.playable and m.href == m.get_player_url() and m.slides_url == reverse("courses:preview", args=[m.key])
    resp = client.get(m.slides_url)
    assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"
    assert resp["Content-Disposition"].startswith("inline") and b"".join(resp.streaming_content) == b"%PDF-1.4 fake"
    # the original is still what "Download" sends
    assert client.get(m.get_download_url())["Content-Type"].startswith("application/vnd.openxmlformats")


def test_failed_conversion_keeps_the_item(client, editor, folder, settings, tmp_path):
    fake_soffice(settings, tmp_path, "exit 1")
    upload(client, folder, "Workshop.pptx", PPTX)
    m = CourseMaterial.objects.get()
    assert not m.preview and "kunne ikke læse" in m.preview_error and not m.playable
    html = client.get(m.get_player_url()).content.decode()
    assert "kan ikke vises her endnu" in html and "Lav visning" in html and m.get_download_url() in html


def test_missing_libreoffice_and_timeout(client, editor, folder, settings, tmp_path):
    upload(client, folder, "Workshop.pptx", PPTX)
    assert "ikke installeret" in CourseMaterial.objects.get().preview_error
    CourseMaterial.objects.all().delete()
    fake_soffice(settings, tmp_path, "sleep 5")
    settings.COURSE_CONVERT_TIMEOUT = 1
    upload(client, folder, "Workshop.pptx", PPTX)
    assert "opgivet" in CourseMaterial.objects.get().preview_error


def test_not_a_pdf_is_refused(client, editor, folder, settings, tmp_path):
    fake_soffice(settings, tmp_path, 'echo "<html>" > "$OUT/slides.pdf"')
    upload(client, folder, "Workshop.pptx", PPTX)
    m = CourseMaterial.objects.get()
    assert not m.preview and "gyldig PDF" in m.preview_error


def test_retry_conversion(client, editor, folder, settings, tmp_path):
    upload(client, folder, "Workshop.pptx", PPTX)
    m = CourseMaterial.objects.get()
    fake_soffice(settings, tmp_path, 'printf "%%PDF-1.4 ok" > "$OUT/slides.pdf"')
    resp = client.post(reverse("courses:material-convert", args=[m.key]))
    m.refresh_from_db()
    assert resp["Location"] == m.get_player_url() and m.preview and m.preview_error == ""


def test_retry_needs_an_editor(client, folder):
    m = CourseMaterial.objects.create(folder=folder, kind="slides", title="x", file="ab/x.pptx", original_name="x.pptx")
    resp = client.post(reverse("courses:material-convert", args=[m.key]))
    assert resp.status_code == 302 and "/login" in resp["Location"]
    User.objects.create_user("v", password="x").groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(User.objects.get(username="v"))
    assert client.post(reverse("courses:material-convert", args=[m.key])).status_code == 403


def test_delete_removes_preview(client, editor, folder, settings, tmp_path):
    fake_soffice(settings, tmp_path, 'printf "%%PDF-1.4 fake" > "$OUT/slides.pdf"')
    upload(client, folder, "Workshop.pptx", PPTX)
    m = CourseMaterial.objects.get()
    paths = [m.file.path, m.preview.path]
    client.post(reverse("courses:material-delete", args=[m.key]))
    assert not any(os.path.exists(p) for p in paths)


def test_management_command_converts_missing(client, editor, folder, settings, tmp_path):
    from django.core.management import call_command

    upload(client, folder, "Workshop.pptx", PPTX)
    fake_soffice(settings, tmp_path, 'printf "%%PDF-1.4 fake" > "$OUT/slides.pdf"')
    out = io.StringIO()
    call_command("course_previews", stdout=out, stderr=io.StringIO())
    assert "1 converted, 0 failed" in out.getvalue() and CourseMaterial.objects.get().preview


# --- player ---------------------------------------------------------------------


def test_player_video_with_playlist(client, editor, folder):
    upload(client, folder, "Guide.pdf", PDF)
    upload(client, folder, "Intro.mp4", MP4)
    upload(client, folder, "Del 2.mp4", MP4)
    client.post(reverse("courses:material-add", args=[folder.slug]), {"url": "https://example.test", "title": "Academy"})
    intro = CourseMaterial.objects.get(title="Intro")
    resp = client.get(intro.get_player_url())
    html = resp.content.decode()
    assert resp.status_code == 200 and resp["X-Robots-Tag"] == "noindex, nofollow"
    assert f'src="{intro.get_file_url()}"' in html and 'data-rate="1.5"' in html and "course-player.js" in html
    # playlist: videos first, then the PDF; no links
    assert html.index(">Intro<") < html.index(">Del 2<") < html.index(">Guide<") and ">Academy<" not in html
    assert "1 af 3" in html and "Næste →" in html and "← Forrige" not in html


def test_player_pdf_uses_slide_viewer(client, editor, folder):
    upload(client, folder, "Guide.pdf", PDF)
    m = CourseMaterial.objects.get()
    html = client.get(m.get_player_url()).content.decode()
    assert f'data-src="{m.get_file_url()}"' in html and "pdfjs/pdf.min.mjs" in html and "pdf.worker.min.mjs" in html


def test_player_is_public_and_guards_keys(client, editor, folder):
    upload(client, folder, "Intro.mp4", MP4)
    m = CourseMaterial.objects.get()
    other = CourseFolder.objects.create(name="Andet")
    client.logout()
    assert client.get(m.get_player_url()).status_code == 200
    assert client.get(reverse("courses:player", args=[other.slug, m.key])).status_code == 404
    link = CourseMaterial.objects.create(folder=folder, kind="link", title="x", url="https://example.test/a")
    resp = client.get(reverse("courses:player", args=[folder.slug, link.key]))
    assert resp.status_code == 302 and resp["Location"] == "https://example.test/a"


def test_folder_page_links_to_player(client, editor, folder):
    upload(client, folder, "Intro.mp4", MP4)
    upload(client, folder, "Guide.pdf", PDF)
    html = client.get(folder.get_absolute_url()).content.decode()
    for m in CourseMaterial.objects.all():
        assert f'href="{m.get_player_url()}"' in html
    assert ">Afspil<" in html and ">Vis<" in html
