"""Reports (0.17.0, FR #14): standalone HTML pages under "Rapporter", with a
public token link that needs no login while the report is marked public."""

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import APIKey
from apps.reports.models import Report

pytestmark = pytest.mark.django_db

HTML = "<title>Test</title><style>body{background:#123}</style><h1>Hej</h1><script>document.title='x'</script>"


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def viewer(client):
    user = User.objects.create_user("viewer", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    client.force_login(user)
    return user


@pytest.fixture
def report(db):
    return Report.objects.create(title="Oktober 2026 – et kig et år tilbage", html=HTML, description="Årsgennemgang")


@pytest.fixture
def write_key():
    user = User.objects.create_user("api", password="x")
    _, raw = APIKey.generate(user=user, scope=APIKey.Scope.WRITE, label="test")
    return raw


# --- model ---------------------------------------------------------------------


def test_slug_is_ascii_and_unique(report):
    assert report.slug == "oktober-2026-et-kig-et-aar-tilbage"
    second = Report.objects.create(title="Oktober 2026 – et kig et år tilbage", html="x")
    assert second.slug == "oktober-2026-et-kig-et-aar-tilbage-2"


def test_token_is_long_and_rotates(report):
    assert len(report.public_token) >= 32
    old = report.public_token
    report.rotate_token()
    assert report.public_token != old


# --- rendering -----------------------------------------------------------------


def test_report_renders_without_site_chrome(client, editor, report):
    response = client.get(report.get_absolute_url())
    body = response.content.decode()
    assert response.status_code == 200
    assert body.startswith("<!doctype html>")
    assert "<h1>Hej</h1>" in body
    assert "nav-shell" not in body and "data-event" not in body  # no Chronicle nav or theme
    assert response["X-Robots-Tag"].startswith("noindex")


def test_full_document_is_served_as_is(client, editor):
    r = Report.objects.create(title="Full", html="<!DOCTYPE html><html><body>full</body></html>")
    body = client.get(r.get_absolute_url()).content.decode()
    assert body.count("<html") == 1 and body.startswith("<!DOCTYPE html>")


def test_list_and_private_view_require_login(client, report):
    assert client.get(reverse("reports:list")).status_code == 302
    response = client.get(report.get_absolute_url())
    assert response.status_code == 302 and "/accounts/login/" in response["Location"]


def test_public_report_slug_url_opens_without_login(client, report):
    report.is_public = True
    report.save()
    response = client.get(report.get_absolute_url())
    assert response.status_code == 200 and "<h1>Hej</h1>" in response.content.decode()
    assert response["Cache-Control"] == "private, no-store"


# --- public link -----------------------------------------------------------------


def test_private_report_public_link_is_404(client, report):
    assert report.is_public is False
    assert client.get(report.get_public_path()).status_code == 404


def test_public_report_opens_without_login(client, report):
    report.is_public = True
    report.save()
    response = client.get(report.get_public_path())
    assert response.status_code == 200
    assert "<h1>Hej</h1>" in response.content.decode()
    assert response["Cache-Control"] == "private, no-store"
    assert response["Referrer-Policy"] == "no-referrer"


def test_wrong_token_is_404(client, report):
    report.is_public = True
    report.save()
    assert client.get(reverse("reports:public", kwargs={"token": "x" * 32})).status_code == 404


def test_making_private_kills_the_link(client, editor, report):
    report.is_public = True
    report.save()
    client.post(reverse("reports:visibility", kwargs={"slug": report.slug}), {"public": "0"})
    client.logout()
    assert client.get(report.get_public_path()).status_code == 404
    assert client.get(report.get_absolute_url()).status_code == 302


# --- editing -----------------------------------------------------------------------


def test_list_shows_public_link_and_actions_to_editors(client, editor, report):
    report.is_public = True
    report.save()
    html = client.get(reverse("reports:list")).content.decode()
    assert report.get_absolute_url() in html
    assert "Kopiér link" in html and "Gør privat" in html and "Læg en rapport op" in html


def test_viewer_sees_list_but_no_actions(client, viewer, report):
    html = client.get(reverse("reports:list")).content.decode()
    assert report.title in html
    assert "Gør offentlig" not in html and "Læg en rapport op" not in html
    assert client.post(reverse("reports:visibility", kwargs={"slug": report.slug}), {"public": "1"}).status_code == 403


def test_upload_creates_and_replace_keeps_link(client, editor):
    f = SimpleUploadedFile("rapport.html", HTML.encode(), content_type="text/html")
    client.post(reverse("reports:upload"), {"title": "Ny rapport", "description": "d", "is_public": "on", "file": f})
    r = Report.objects.get(title="Ny rapport")
    assert r.is_public and r.created_by == editor and "<h1>Hej</h1>" in r.html
    token = r.public_token
    f2 = SimpleUploadedFile("rapport2.html", b"<p>v2</p>", content_type="text/html")
    client.post(reverse("reports:upload"), {"title": "Ny rapport v2", "description": "", "file": f2, "replace": r.slug})
    r.refresh_from_db()
    assert r.title == "Ny rapport v2" and r.html == "<p>v2</p>" and r.public_token == token and r.is_public is False


def test_upload_rejects_non_html(client, editor):
    f = SimpleUploadedFile("x.pdf", b"%PDF", content_type="application/pdf")
    client.post(reverse("reports:upload"), {"title": "Pdf", "file": f})
    assert not Report.objects.filter(title="Pdf").exists()


# --- API -----------------------------------------------------------------------------


def test_api_upsert_and_list(client, write_key):
    url = reverse("api:report-upsert", kwargs={"slug": "oktober-2026"})
    body = {"title": "Oktober 2026", "description": "Årsgennemgang", "html": HTML, "is_public": True}
    response = client.put(url, data=body, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {write_key}")
    assert response.status_code == 201, response.content
    data = response.json()["report"]
    assert data["slug"] == "oktober-2026" and data["is_public"] is True and data["public_url"].endswith(f"/reports/p/{data['public_token']}/")
    # second PUT updates in place and keeps the token
    response = client.put(url, data={**body, "title": "Oktober 2026 v2"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {write_key}")
    assert response.status_code == 200 and response.json()["report"]["public_token"] == data["public_token"]
    assert Report.objects.get(slug="oktober-2026").title == "Oktober 2026 v2"
    listing = client.get(reverse("api:reports-list"), HTTP_AUTHORIZATION=f"Bearer {write_key}").json()
    assert [r["slug"] for r in listing["reports"]] == ["oktober-2026"]


def test_api_requires_write_key_and_fields(client, write_key):
    url = reverse("api:report-upsert", kwargs={"slug": "x"})
    assert client.put(url, data={"title": "t"}, content_type="application/json").status_code == 401
    bad = client.put(url, data={"title": "t"}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {write_key}")
    assert bad.status_code == 400


# --- video (0.18.0) -----------------------------------------------------------------


MP4 = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40  # 10 KB of fake mp4


@pytest.fixture
def files_dir(settings, tmp_path):
    settings.REPORT_FILES_DIR = tmp_path / "report_files"
    return settings.REPORT_FILES_DIR


def test_video_upload_via_form_and_serving(client, editor, files_dir):
    f = SimpleUploadedFile("r.html", HTML.encode(), content_type="text/html")
    v = SimpleUploadedFile("film.mp4", MP4, content_type="video/mp4")
    client.post(reverse("reports:upload"), {"title": "Med video", "file": f, "video": v})
    r = Report.objects.get(title="Med video")
    assert r.video and (files_dir / r.slug / "video.mp4").exists()
    # inline
    resp = client.get(r.get_video_path())
    assert resp.status_code == 200 and resp["Content-Type"] == "video/mp4" and resp["Accept-Ranges"] == "bytes"
    assert resp["Content-Disposition"].startswith("inline") and b"".join(resp.streaming_content) == MP4
    # download
    resp = client.get(r.get_video_path() + "?download=1")
    assert resp["Content-Disposition"] == f'attachment; filename="{r.slug}.mp4"'
    # range
    resp = client.get(r.get_video_path(), HTTP_RANGE="bytes=100-199")
    assert resp.status_code == 206 and resp["Content-Range"] == f"bytes 100-199/{len(MP4)}" and b"".join(resp.streaming_content) == MP4[100:200]
    resp = client.get(r.get_video_path(), HTTP_RANGE=f"bytes={len(MP4) + 5}-")
    assert resp.status_code == 416


def test_video_access_follows_report_visibility(client, report, files_dir):
    report.video.save("video.mp4", SimpleUploadedFile("v.mp4", MP4), save=True)
    assert client.get(report.get_video_path()).status_code == 302  # private: login
    assert client.get(reverse("reports:public-video", kwargs={"token": report.public_token})).status_code == 404
    report.is_public = True
    report.save()
    assert client.get(report.get_video_path()).status_code == 200
    assert client.get(reverse("reports:public-video", kwargs={"token": report.public_token})).status_code == 200


def test_video_missing_is_404(client, editor, report):
    assert client.get(report.get_video_path()).status_code == 404


def test_api_video_upload(client, write_key, report, files_dir):
    url = reverse("api:report-video-upload", kwargs={"slug": report.slug})
    assert client.put(url, data=MP4, content_type="application/octet-stream", HTTP_AUTHORIZATION=f"Bearer {write_key}").status_code == 415
    resp = client.put(url, data=MP4, content_type="video/mp4", HTTP_AUTHORIZATION=f"Bearer {write_key}")
    assert resp.status_code == 200 and resp.json()["report"]["has_video"] is True
    report.refresh_from_db()
    assert report.video.read() == MP4
    # replacing keeps one file
    client.put(url, data=MP4[:500], content_type="video/mp4", HTTP_AUTHORIZATION=f"Bearer {write_key}")
    report.refresh_from_db()
    assert report.video.size == 500 and len(list((files_dir / report.slug).iterdir())) == 1
    assert client.put(reverse("api:report-video-upload", kwargs={"slug": "nope"}), data=MP4, content_type="video/mp4", HTTP_AUTHORIZATION=f"Bearer {write_key}").status_code == 404


def test_api_video_upload_above_memory_cap(client, write_key, report, files_dir, settings):
    """A real video is far above DATA_UPLOAD_MAX_MEMORY_SIZE; the upload must stream, not buffer."""
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
    big = MP4 * 400  # ~4 MB
    url = reverse("api:report-video-upload", kwargs={"slug": report.slug})
    resp = client.put(url, data=big, content_type="video/mp4", HTTP_AUTHORIZATION=f"Bearer {write_key}")
    assert resp.status_code == 200, resp.content[:200]
    report.refresh_from_db()
    assert report.video.size == len(big)
