"""Fetch course material from a link ("Hent fra link").

An editor gives a direct link to a video, presentation or PDF; Chronicle
downloads it in a background thread of the web process and files it in
the folder exactly as if it had been uploaded (same type and size checks,
presentations converted for the player). Progress lives on a
``CourseImport`` row that the folder page polls.

The web container sits inside the FynBus network, so a server-side fetch
could otherwise be pointed at internal services. Every hop is checked:
the host must resolve only to public addresses, redirects are followed by
hand (each new address checked again, at most five), and after connecting
the peer address is checked once more, so a DNS answer that changes
between check and connect is caught before the body is read.
"""

import ipaddress
import logging
import socket
import threading
import time
from email.message import Message
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

import requests
from django.conf import settings
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.db import close_old_connections, connection
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from .filetypes import TYPES, content_matches, extension
from .models import CourseImport, CourseMaterial

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
CHUNK = 1024 * 1024
PROGRESS_EVERY = 2.0  # seconds between progress writes

# Content-Type → extension, for links whose path has no usable extension.
_EXT_FOR_TYPE = {
    "video/mp4": ".mp4",
    "video/x-m4v": ".m4v",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow": ".ppsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.oasis.opendocument.presentation": ".odp",
}


class FetchError(Exception):
    """A reason, in Danish, why the link cannot be fetched."""


def _resolve(host: str, port: int) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]


def _is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def check_url(url: str) -> None:
    """Raise FetchError unless ``url`` is http(s) to a host with only public addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Linket skal begynde med http:// eller https://.")
    if parts.username or parts.password:
        raise FetchError("Linket må ikke indeholde brugernavn eller adgangskode.")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise FetchError("Linket har et ugyldigt portnummer.") from None
    try:
        addrs = _resolve(parts.hostname, port)
    except (socket.gaierror, UnicodeError):
        raise FetchError(f"Serveren {parts.hostname} findes ikke.") from None
    if not addrs or not all(_is_public(a) for a in addrs):
        raise FetchError("Linket peger på en intern adresse og kan ikke hentes herfra.")


def _peer_address(resp) -> str | None:
    """The IP the response actually came from, if urllib3 still exposes it."""
    try:
        return resp.raw._connection.sock.getpeername()[0]
    except Exception:  # noqa: BLE001 - best effort, the pre-connect check already ran
        return None


def _filename(resp, url: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    if cd:
        msg = Message()
        msg["Content-Disposition"] = cd
        name = msg.get_filename()
        if name:
            return PurePosixPath(name.replace("\\", "/")).name[:200]
    return PurePosixPath(unquote(urlsplit(url).path)).name[:200] or "fil"


def _open(session, url: str):
    """GET ``url`` following up to MAX_REDIRECTS redirects, checking every hop."""
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        resp = session.get(url, stream=True, allow_redirects=False, timeout=(10, 60))
        peer = _peer_address(resp)
        if peer and not _is_public(peer):
            resp.close()
            raise FetchError("Linket peger på en intern adresse og kan ikke hentes herfra.")
        if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
            url = urljoin(url, resp.headers["Location"])
            resp.close()
            continue
        return resp, url
    raise FetchError("Linket sender videre for mange gange.")


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # never route through an environment proxy to internal hosts
    s.headers["User-Agent"] = "FynBus-Chronicle (kursusmateriale)"
    return s


def _download(imp: CourseImport) -> CourseMaterial:
    session = _session()
    try:
        resp, final_url = _open(session, imp.url)
    except requests.RequestException:
        raise FetchError("Serveren svarede ikke.") from None
    with resp:
        if resp.status_code != 200:
            raise FetchError(f"Serveren svarede {resp.status_code}.")
        name = _filename(resp, final_url)
        ext = extension(name)
        ctype = resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if ext not in TYPES:
            ext = _EXT_FOR_TYPE.get(ctype, "")
            if not ext:
                if ctype.startswith("text/html"):
                    raise FetchError("Linket peger på en webside, ikke en fil. Brug et direkte link til filen, eller tilføj det som et link.")
                raise FetchError("Linket peger ikke på en video, PowerPoint eller PDF.")
            name = f"{PurePosixPath(name).stem or 'fil'}{ext}"
        ft = TYPES[ext]
        limit = settings.COURSE_FILE_MAX_BYTES
        total = resp.headers.get("Content-Length")
        total = int(total) if total and total.isdigit() else None
        if total and total > limit:
            raise FetchError(f"Filen er større end {filesizeformat(limit)}.")
        CourseImport.objects.filter(pk=imp.pk).update(bytes_total=total, updated_at=timezone.now())

        tmp = NamedTemporaryFile(suffix=ext)
        done, last = 0, time.monotonic()
        try:
            for chunk in resp.iter_content(CHUNK):
                done += len(chunk)
                if done > limit:
                    raise FetchError(f"Filen er større end {filesizeformat(limit)}.")
                tmp.write(chunk)
                if time.monotonic() - last >= PROGRESS_EVERY:
                    last = time.monotonic()
                    CourseImport.objects.filter(pk=imp.pk).update(bytes_done=done, updated_at=timezone.now())
        except requests.RequestException:
            tmp.close()
            raise FetchError("Forbindelsen blev afbrudt under hentningen.") from None
        except FetchError:
            tmp.close()
            raise
    if done == 0:
        tmp.close()
        raise FetchError("Filen er tom.")
    tmp.flush()
    if not content_matches(ext, tmp):
        tmp.close()
        raise FetchError(f"Filen ligner ikke en {ext[1:].upper()}-fil.")
    item = CourseMaterial(
        folder=imp.folder, kind=ft.kind, title=(imp.title or PurePosixPath(name).stem)[:200],
        description=imp.description, original_name=name[:255], size=done, added_by=imp.created_by,
    )
    tmp.seek(0)
    with tmp:
        item.file.save(name, File(tmp), save=False)
        item.save()
    if item.kind == CourseMaterial.Kind.SLIDES:
        from .convert import make_preview

        make_preview(item)
    return item


def run(import_pk: int) -> None:
    """Fetch one import; on success the import row is replaced by the material."""
    close_old_connections()
    try:
        imp = CourseImport.objects.select_related("folder", "created_by").get(pk=import_pk)
        CourseImport.objects.filter(pk=imp.pk).update(
            status=CourseImport.Status.RUNNING, error="", bytes_done=0, bytes_total=None, updated_at=timezone.now()
        )
        try:
            _download(imp)
        except FetchError as e:
            CourseImport.objects.filter(pk=imp.pk).update(status=CourseImport.Status.FAILED, error=str(e)[:300], updated_at=timezone.now())
            return
        except Exception:
            logger.exception("courses: import %s failed", imp.pk)
            CourseImport.objects.filter(pk=imp.pk).update(
                status=CourseImport.Status.FAILED, error="Hentningen fejlede uventet.", updated_at=timezone.now()
            )
            return
        imp.delete()
    except CourseImport.DoesNotExist:
        return  # removed while it ran


def _run_in_thread(import_pk: int) -> None:
    try:
        run(import_pk)
    finally:
        connection.close()  # this thread's own connection; never the request's


def start(imp: CourseImport) -> None:
    """Run the import in a background thread (inline when COURSE_IMPORT_INLINE, for tests)."""
    if getattr(settings, "COURSE_IMPORT_INLINE", False):
        run(imp.pk)
        return
    threading.Thread(target=_run_in_thread, args=(imp.pk,), name=f"course-import-{imp.pk}", daemon=True).start()

