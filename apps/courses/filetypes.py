"""Which files the course material accepts, and how to tell them apart.

A file is accepted on its extension *and* its first bytes, so a renamed
executable is refused. Each accepted extension maps to the material kind
and to the Content-Type it is served with.
"""

import zipfile
from dataclasses import dataclass

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy Office (.ppt/.pps)
ZIP_MAGIC = b"PK\x03\x04"
EBML_MAGIC = b"\x1a\x45\xdf\xa3"  # WebM / Matroska
# ISO base media (mp4, m4v, mov) puts a box type at bytes 4..8. Files from
# older QuickTime can start with another top-level box than ftyp.
ISO_BOXES = {b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip"}
ODP_MIMETYPE = b"application/vnd.oasis.opendocument.presentation"


@dataclass(frozen=True)
class FileType:
    kind: str  # CourseMaterial.Kind value
    content_type: str
    label: str


TYPES: dict[str, FileType] = {
    ".mp4": FileType("video", "video/mp4", "MP4"),
    ".m4v": FileType("video", "video/mp4", "M4V"),
    ".mov": FileType("video", "video/quicktime", "MOV"),
    ".webm": FileType("video", "video/webm", "WebM"),
    ".pdf": FileType("pdf", "application/pdf", "PDF"),
    ".pptx": FileType("slides", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "PowerPoint"),
    ".ppsx": FileType("slides", "application/vnd.openxmlformats-officedocument.presentationml.slideshow", "PowerPoint"),
    ".ppt": FileType("slides", "application/vnd.ms-powerpoint", "PowerPoint"),
    ".pps": FileType("slides", "application/vnd.ms-powerpoint", "PowerPoint"),
    ".odp": FileType("slides", "application/vnd.oasis.opendocument.presentation", "ODP"),
}

ACCEPT = ",".join(sorted(TYPES))


def extension(name: str) -> str:
    """Lower-case extension with its dot, or "" if the name has none."""
    name = (name or "").lower()
    dot = name.rfind(".")
    return name[dot:] if dot > 0 else ""


def content_matches(ext: str, f) -> bool:
    """True if the start of the file looks like what ``ext`` promises.

    ``f`` is a file-like object; it is read from the start and rewound.
    """
    f.seek(0)
    head = f.read(16)
    try:
        if ext in (".mp4", ".m4v", ".mov"):
            return len(head) >= 8 and head[4:8] in ISO_BOXES
        if ext == ".webm":
            return head.startswith(EBML_MAGIC)
        if ext == ".pdf":
            return head.startswith(b"%PDF-")
        if ext in (".ppt", ".pps"):
            return head.startswith(OLE_MAGIC)
        if ext in (".pptx", ".ppsx", ".odp"):
            if not head.startswith(ZIP_MAGIC):
                return False
            f.seek(0)
            try:
                with zipfile.ZipFile(f) as z:
                    names = set(z.namelist())
                    if ext == ".odp":
                        return "mimetype" in names and z.read("mimetype").strip() == ODP_MIMETYPE
                    return "ppt/presentation.xml" in names
            except (zipfile.BadZipFile, KeyError, OSError):
                return False
        return False
    finally:
        f.seek(0)
