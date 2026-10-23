"""Read Outlook .msg files (e.g. FE-CSIRT advisories mailed as attachments).

A .msg file is an OLE compound file (MS-CFB) holding MAPI properties
([MS-OXMSG]). We read just what the CVE page needs, with ``olefile``
(BSD licence; the usual alternative, extract-msg, is GPL and would end up in
the published Docker image):

* headers: subject, sender, To/Cc display strings, sent/received time;
* the text body (PR_BODY), or the HTML body reduced to plain text;
* attachments by-value: filename, MIME type and bytes (so PDFs inside the
  mail can be stored as their own CVE attachments).

Nothing here renders HTML: the body is returned as plain text and the page
shows it escaped. Embedded messages, OLE objects and RTF-only bodies are
skipped rather than interpreted.
"""

from __future__ import annotations

import html
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone
from html.parser import HTMLParser

import olefile

# MAPI property ids ([MS-OXPROPS]).
PR_SUBJECT = 0x0037
PR_CLIENT_SUBMIT_TIME = 0x0039
PR_MESSAGE_DELIVERY_TIME = 0x0E06
PR_SENDER_NAME = 0x0C1A
PR_SENDER_EMAIL_ADDRESS = 0x0C1F
PR_SENDER_SMTP_ADDRESS = 0x5D01
PR_DISPLAY_TO = 0x0E04
PR_DISPLAY_CC = 0x0E03
PR_BODY = 0x1000
PR_BODY_HTML = 0x1013
PR_ATTACH_DATA_BIN = 0x3701
PR_ATTACH_FILENAME = 0x3704
PR_ATTACH_LONG_FILENAME = 0x3707
PR_ATTACH_METHOD = 0x3705
PR_ATTACH_MIME_TAG = 0x370E
PR_DISPLAY_NAME = 0x3001

PT_STRING8, PT_UNICODE, PT_BINARY, PT_SYSTIME = 0x001E, 0x001F, 0x0102, 0x0040
ATTACH_BY_VALUE = 1

MAX_BODY_CHARS = 200_000
MAX_ATTACHMENTS = 50


class MsgError(ValueError):
    """Not a readable Outlook message."""


@dataclass
class MsgAttachment:
    filename: str
    mime_type: str
    data: bytes

    @property
    def is_pdf(self) -> bool:
        return self.data[:5] == b"%PDF-"


@dataclass
class MsgInfo:
    subject: str = ""
    sender: str = ""
    to: str = ""
    cc: str = ""
    sent: datetime | None = None
    body: str = ""
    attachments: list[MsgAttachment] = field(default_factory=list)


def is_msg(head: bytes) -> bool:
    """True if the bytes start like an OLE compound file (all .msg files do)."""
    return head[:8] == olefile.MAGIC


class _TextFromHTML(HTMLParser):
    """Collect visible text from an HTML body (no rendering, no scripts)."""

    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    p = _TextFromHTML()
    p.feed(raw)
    text = html.unescape("".join(p.parts))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _filetime(value: int) -> datetime | None:
    if not value:
        return None
    try:
        return datetime(1601, 1, 1, tzinfo=dt_timezone.utc) + timedelta(microseconds=value // 10)
    except OverflowError:
        return None


class _Reader:
    def __init__(self, ole: olefile.OleFileIO):
        self.ole = ole

    def stream(self, *path: str) -> bytes | None:
        name = "/".join(path)
        return self.ole.openstream(name).read() if self.ole.exists(name) else None

    def string(self, prop: int, prefix: str = "") -> str:
        """A string property, Unicode (001F) first, then 8-bit (001E)."""
        for ptype, codec in ((PT_UNICODE, "utf-16-le"), (PT_STRING8, "cp1252")):
            raw = self.stream(*(p for p in (prefix, f"__substg1.0_{prop:04X}{ptype:04X}") if p))
            if raw is not None:
                return raw.decode(codec, errors="replace").rstrip("\x00").strip()
        return ""

    def binary(self, prop: int, prefix: str = "") -> bytes | None:
        return self.stream(*(p for p in (prefix, f"__substg1.0_{prop:04X}{PT_BINARY:04X}") if p))

    def fixed(self, prefix: str = "", header: int = 32) -> dict[int, tuple[int, bytes]]:
        """Fixed-size properties from a __properties_version1.0 stream.

        Header is 32 bytes for the top-level message, 8 for attachments;
        then 16-byte entries: type (2), id (2), flags (4), value (8).
        """
        raw = self.stream(*(p for p in (prefix, "__properties_version1.0") if p)) or b""
        props: dict[int, tuple[int, bytes]] = {}
        for off in range(header, len(raw) - 15, 16):
            ptype, pid = struct.unpack_from("<HH", raw, off)
            props[pid] = (ptype, raw[off + 8: off + 16])
        return props


def parse(fileobj) -> MsgInfo:
    """Parse a .msg file object. Raises MsgError if it isn't a readable message."""
    head = fileobj.read(8)
    fileobj.seek(0)
    if not is_msg(head):
        raise MsgError("not an OLE compound file")
    try:
        ole = olefile.OleFileIO(fileobj)
    except Exception as exc:  # olefile raises plain OSError/ValueError subclasses
        raise MsgError(f"unreadable compound file: {exc.__class__.__name__}") from None
    try:
        r = _Reader(ole)
        if not ole.exists("__properties_version1.0"):
            raise MsgError("no MAPI properties (not an Outlook message)")
        info = MsgInfo()
        info.subject = r.string(PR_SUBJECT)
        name = r.string(PR_SENDER_NAME)
        address = r.string(PR_SENDER_SMTP_ADDRESS) or r.string(PR_SENDER_EMAIL_ADDRESS)
        if address and "@" not in address:
            address = ""  # an Exchange X.500 DN, not useful to show
        info.sender = f"{name} <{address}>" if name and address and name != address else (name or address)
        info.to = r.string(PR_DISPLAY_TO)
        info.cc = r.string(PR_DISPLAY_CC)
        fixed = r.fixed()
        for pid in (PR_CLIENT_SUBMIT_TIME, PR_MESSAGE_DELIVERY_TIME):
            ptype, value = fixed.get(pid, (0, b""))
            if ptype == PT_SYSTIME:
                info.sent = _filetime(struct.unpack("<Q", value)[0])
                if info.sent:
                    break
        body = r.string(PR_BODY)
        if not body:
            raw_html = r.binary(PR_BODY_HTML)
            if raw_html is None:
                raw_html_text = r.string(PR_BODY_HTML)
            else:
                raw_html_text = raw_html.decode("utf-8", errors="replace")
            body = html_to_text(raw_html_text) if raw_html_text else ""
        info.body = body[:MAX_BODY_CHARS]
        storages = sorted(
            {e[0] for e in ole.listdir(streams=True, storages=True) if e and e[0].startswith("__attach_version1.0_")}
        )
        for storage in storages[:MAX_ATTACHMENTS]:
            method = r.fixed(storage, header=8).get(PR_ATTACH_METHOD, (0, b"\0" * 8))[1]
            if struct.unpack_from("<I", method)[0] not in (ATTACH_BY_VALUE, 0):
                continue  # embedded message / OLE object / reference: not by value
            data = r.binary(PR_ATTACH_DATA_BIN, storage)
            if not data:
                continue
            filename = (r.string(PR_ATTACH_LONG_FILENAME, storage) or r.string(PR_ATTACH_FILENAME, storage)
                        or r.string(PR_DISPLAY_NAME, storage) or "vedhaeftning")
            info.attachments.append(MsgAttachment(filename=filename, mime_type=r.string(PR_ATTACH_MIME_TAG, storage), data=data))
        return info
    finally:
        ole.close()


TLP_RE = re.compile(r"TLP\s*[:\-]?\s*(CLEAR|WHITE|GREEN|AMBER\s*\+\s*STRICT|AMBER|RED)\b", re.IGNORECASE)


def detect_tlp(*texts: str) -> str:
    """The first TLP marking in the given texts, as a CVEAttachment.TLP value, or ''."""
    for text in texts:
        m = TLP_RE.search(text or "")
        if m:
            label = re.sub(r"\s+", "", m.group(1).upper())
            return {"CLEAR": "clear", "WHITE": "clear", "GREEN": "green", "AMBER": "amber",
                    "AMBER+STRICT": "amber_strict", "RED": "red"}[label]
    return ""
