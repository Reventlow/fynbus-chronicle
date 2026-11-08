"""Hent fra link (1.20.1): the server fetches a file from a link into a
folder. DNS and HTTP are faked; nothing leaves the test."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.courses import fetch
from apps.courses.models import CourseFolder, CourseImport, CourseMaterial

pytestmark = pytest.mark.django_db

MP4 = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40
PDF = b"%PDF-1.7\n" + b"x" * 500

# host -> addresses, for the fake resolver
DNS = {
    "files.example.com": ["93.184.215.14"],
    "cdn.example.com": ["93.184.215.15"],
    "intranet.example.com": ["10.2.64.214"],
    "localhost": ["127.0.0.1"],
    "mixed.example.com": ["93.184.215.16", "192.168.1.5"],
    "v6local.example.com": ["::ffff:10.0.0.1"],
}


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.raw = None  # no peer address exposed: the pre-connect check is what runs

    def iter_content(self, size):
        for i in range(0, len(self._body), 7):
            yield self._body[i:i + 7]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, **kw):
        self.calls.append(url)
        assert kw["allow_redirects"] is False and kw["stream"] is True
        return self.routes[url]


@pytest.fixture(autouse=True)
def setup(settings, tmp_path, monkeypatch):
    settings.COURSE_FILES_DIR = tmp_path / "course_files"
    settings.COURSE_SOFFICE = str(tmp_path / "no-soffice")
    settings.COURSE_IMPORT_INLINE = True

    def resolve(host, port):
        if host not in DNS:
            import socket

            raise socket.gaierror
        return DNS[host]

    monkeypatch.setattr(fetch, "_resolve", resolve)


@pytest.fixture
def web(monkeypatch):
    routes = {}
    session = FakeSession(routes)
    monkeypatch.setattr(fetch, "_session", lambda: session)
    return routes


@pytest.fixture
def editor(client):
    user = User.objects.create_user("gre", password="x")
    client.force_login(user)
    return user


@pytest.fixture
def folder(db):
    return CourseFolder.objects.create(name="Anthropic")


def add(client, folder, url, **extra):
    return client.post(reverse("courses:material-add", args=[folder.slug]), {"fetch_url": url, **extra}, HTTP_HX_REQUEST="true")


def test_fetch_video(client, editor, folder, web):
    web["https://files.example.com/kurser/Modul%201.mp4"] = FakeResponse(body=MP4, headers={"Content-Length": str(len(MP4))})
    resp = add(client, folder, "https://files.example.com/kurser/Modul%201.mp4", description="d")
    assert resp.status_code == 204 and resp["HX-Redirect"] == folder.get_absolute_url()
    m = CourseMaterial.objects.get()
    assert m.kind == "video" and m.title == "Modul 1" and m.original_name == "Modul 1.mp4" and m.size == len(MP4)
    assert m.description == "d" and m.added_by == editor and m.file.read() == MP4
    assert not CourseImport.objects.exists()


def test_redirect_and_content_disposition(client, editor, folder, web):
    web["https://files.example.com/share/abc?download=1"] = FakeResponse(302, headers={"Location": "https://cdn.example.com/blob/123"})
    web["https://cdn.example.com/blob/123"] = FakeResponse(body=PDF, headers={"Content-Disposition": "attachment; filename*=UTF-8''Kursusbevis%20%C3%A6.pdf"})
    add(client, folder, "https://files.example.com/share/abc?download=1", title="Bevis")
    m = CourseMaterial.objects.get()
    assert m.kind == "pdf" and m.title == "Bevis" and m.original_name == "Kursusbevis æ.pdf"


def test_type_from_content_type(client, editor, folder, web):
    web["https://files.example.com/download"] = FakeResponse(body=MP4, headers={"Content-Type": "video/mp4"})
    add(client, folder, "https://files.example.com/download")
    assert CourseMaterial.objects.get().original_name == "download.mp4"


@pytest.mark.parametrize("url", [
    "https://intranet.example.com/x.mp4",
    "http://localhost:8000/x.mp4",
    "http://127.0.0.1/x.mp4",
    "http://[::1]/x.mp4",
    "https://mixed.example.com/x.mp4",
    "https://v6local.example.com/x.mp4",
])
def test_internal_addresses_are_refused_up_front(client, editor, folder, web, url):
    DNS.setdefault("127.0.0.1", ["127.0.0.1"])
    DNS.setdefault("::1", ["::1"])
    resp = add(client, folder, url)
    assert resp.status_code == 200 and "intern adresse" in resp.content.decode()
    assert not CourseImport.objects.exists() and not CourseMaterial.objects.exists()


def test_redirect_to_internal_address_fails(client, editor, folder, web):
    web["https://files.example.com/x.mp4"] = FakeResponse(302, headers={"Location": "http://intranet.example.com/admin"})
    add(client, folder, "https://files.example.com/x.mp4")
    imp = CourseImport.objects.get()
    assert imp.is_failed and "intern adresse" in imp.error and not CourseMaterial.objects.exists()


def test_redirect_loop_and_bad_scheme(client, editor, folder, web):
    web["https://files.example.com/a"] = FakeResponse(302, headers={"Location": "/a"})
    add(client, folder, "https://files.example.com/a")
    assert "for mange gange" in CourseImport.objects.get().error
    resp = add(client, folder, "ftp://files.example.com/a.mp4")
    assert resp.status_code == 200 and CourseImport.objects.count() == 1


def test_unknown_host(client, editor, folder, web):
    resp = add(client, folder, "https://nope.example.com/a.mp4")
    assert "findes ikke" in resp.content.decode()


@pytest.mark.parametrize("path,response,error", [
    ("/x.mp4", FakeResponse(404), "svarede 404"),
    ("/page", FakeResponse(body=b"<html>", headers={"Content-Type": "text/html; charset=utf-8"}), "webside"),
    ("/blob", FakeResponse(body=b"MZ" + b"\x00" * 99, headers={"Content-Type": "application/octet-stream"}), "ikke på en video"),
    ("/x.mp4", FakeResponse(body=b"hello, not a video"), "ligner ikke en MP4"),
])
def test_fetch_failures_are_shown(client, editor, folder, web, path, response, error):
    url = "https://files.example.com" + path
    web[url] = response
    add(client, folder, url)
    imp = CourseImport.objects.get()
    assert imp.is_failed and error in imp.error and not CourseMaterial.objects.exists()
    html = client.get(folder.get_absolute_url()).content.decode()
    assert "Hentes fra link" in html and error in html and "Prøv igen" in html


def test_size_limit(client, editor, folder, web, settings):
    settings.COURSE_FILE_MAX_BYTES = 1000
    web["https://files.example.com/big.mp4"] = FakeResponse(body=MP4, headers={"Content-Length": str(len(MP4))})
    web["https://files.example.com/sneaky.mp4"] = FakeResponse(body=MP4)  # no Content-Length
    add(client, folder, "https://files.example.com/big.mp4")
    add(client, folder, "https://files.example.com/sneaky.mp4")
    assert all("større end" in i.error for i in CourseImport.objects.all()) and CourseImport.objects.count() == 2
    assert not CourseMaterial.objects.exists()


def test_retry_and_remove(client, editor, folder, web):
    web["https://files.example.com/x.mp4"] = FakeResponse(503)
    add(client, folder, "https://files.example.com/x.mp4")
    imp = CourseImport.objects.get()
    web["https://files.example.com/x.mp4"] = FakeResponse(body=MP4)
    client.post(reverse("courses:import-retry", args=[imp.pk]))
    assert CourseMaterial.objects.count() == 1 and not CourseImport.objects.exists()
    web["https://files.example.com/y.mp4"] = FakeResponse(503)
    add(client, folder, "https://files.example.com/y.mp4")
    client.post(reverse("courses:import-delete", args=[CourseImport.objects.get().pk]))
    assert not CourseImport.objects.exists()


def test_polling_refreshes_when_done(client, editor, folder):
    imp = CourseImport.objects.create(folder=folder, url="https://files.example.com/x.mp4", status="running", bytes_done=5 * 1024 * 1024, bytes_total=10 * 1024 * 1024)
    url = reverse("courses:imports", args=[folder.slug])
    html = client.get(url + f"?watch={imp.pk}").content.decode()
    assert 'hx-trigger="every 2s"' in html and "af 10" in html and 'value="50"' in html
    pk = imp.pk
    imp.delete()
    resp = client.get(url + f"?watch={pk}")
    assert resp.status_code == 204 and resp["HX-Refresh"] == "true"


def test_stalled_import_shows_as_failed(client, editor, folder):
    from django.utils import timezone

    CourseImport.objects.create(folder=folder, url="https://files.example.com/x.mp4", status="running",
                                updated_at=timezone.now() - CourseImport.STALLED_AFTER * 2)
    html = client.get(folder.get_absolute_url()).content.decode()
    assert "blev afbrudt" in html and "Prøv igen" in html and "every 2s" not in html


def test_imports_are_editor_only(client, folder):
    imp = CourseImport.objects.create(folder=folder, url="https://files.example.com/x.mp4", error="boom", status="failed")
    assert "Hentes fra link" not in client.get(folder.get_absolute_url()).content.decode()
    for url in (reverse("courses:imports", args=[folder.slug]), reverse("courses:import-retry", args=[imp.pk]),
                reverse("courses:import-delete", args=[imp.pk])):
        resp = client.post(url) if "imports" not in url and "hentninger" not in url else client.get(url)
        assert resp.status_code == 302 and "/login" in resp["Location"]


def test_check_url_rejects_credentials_in_url():
    with pytest.raises(fetch.FetchError, match="brugernavn"):
        fetch.check_url("https://user:pw@files.example.com/x.mp4")
