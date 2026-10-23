"""Build minimal Outlook .msg files for tests (no real e-mail in the repo).

Writes a standard MS-CFB v3 compound file with the MAPI streams that
``apps.cves.msg`` reads: streams under 4096 bytes go into the mini stream
(64-byte mini sectors, held by the root entry, chained in the mini FAT),
larger ones into regular 512-byte sectors.
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone

SECTOR = 512
ENDOFCHAIN, FREESECT, FATSECT, NOSTREAM = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD, 0xFFFFFFFF


def _str_stream(prop: int, value: str) -> tuple[str, bytes]:
    return f"__substg1.0_{prop:04X}001F", value.encode("utf-16-le")


def _bin_stream(prop: int, value: bytes) -> tuple[str, bytes]:
    return f"__substg1.0_{prop:04X}0102", value


def _filetime(dt: datetime) -> int:
    return int((dt - datetime(1601, 1, 1, tzinfo=timezone.utc)).total_seconds() * 10_000_000)


def build_msg(
    *,
    subject: str = "",
    sender_name: str = "",
    sender_email: str = "",
    to: str = "",
    body: str | None = None,
    html_body: str | None = None,
    sent: datetime | None = None,
    attachments: list[tuple[str, bytes, str]] = (),
) -> bytes:
    """Return the bytes of a .msg with the given headers, body and attachments."""
    top: list[tuple[str, bytes]] = []
    for prop, value in ((0x0037, subject), (0x0C1A, sender_name), (0x5D01, sender_email), (0x0E04, to)):
        if value:
            top.append(_str_stream(prop, value))
    if body is not None:
        top.append(_str_stream(0x1000, body))
    if html_body is not None:
        top.append(_bin_stream(0x1013, html_body.encode("utf-8")))
    props = bytearray(32)  # top-level header
    if sent:
        props += struct.pack("<HHIQ", 0x0040, 0x0039, 6, _filetime(sent))
    top.append(("__properties_version1.0", bytes(props)))
    storages: list[tuple[str, list[tuple[str, bytes]]]] = []
    for i, (filename, data, mime) in enumerate(attachments):
        a_props = bytearray(8) + struct.pack("<HHIQ", 0x0003, 0x3705, 6, 1)  # PR_ATTACH_METHOD = by value
        streams = [_str_stream(0x3707, filename), _bin_stream(0x3701, data), ("__properties_version1.0", bytes(a_props))]
        if mime:
            streams.append(_str_stream(0x370E, mime))
        storages.append((f"__attach_version1.0_#{i:08X}", streams))
    return _write_cfb(top, storages)


def _write_cfb(top: list[tuple[str, bytes]], storages: list[tuple[str, list[tuple[str, bytes]]]]) -> bytes:
    # Directory entries: 0 = root, then top-level streams, then each storage + its streams.
    entries: list[dict] = [{"name": "Root Entry", "type": 5, "children": []}]

    def add(name, etype, data=b""):
        entries.append({"name": name, "type": etype, "data": data, "children": []})
        return len(entries) - 1

    for name, data in top:
        entries[0]["children"].append(add(name, 2, data))
    for sname, streams in storages:
        sid = add(sname, 1)
        entries[0]["children"].append(sid)
        for name, data in streams:
            entries[sid]["children"].append(add(name, 2, data))

    # Sibling chains: each parent's children linked via right-sibling, all black.
    for e in entries:
        e.setdefault("left", NOSTREAM); e.setdefault("right", NOSTREAM); e["child"] = NOSTREAM
    for e in entries:
        kids = e["children"]
        if kids:
            e["child"] = kids[0]
            for a, b in zip(kids, kids[1:]):
                entries[a]["right"] = b

    MINI, CUTOFF = 64, 4096
    # Small streams -> mini stream; record each one's first mini sector.
    mini_stream = bytearray()
    mini_fat: list[int] = []
    for e in entries:
        data = e.get("data", b"")
        if e["type"] == 2 and data and len(data) < CUTOFF:
            count = -(-len(data) // MINI)
            first = len(mini_fat)
            mini_fat += [first + i + 1 for i in range(count - 1)] + [ENDOFCHAIN]
            mini_stream += data.ljust(count * MINI, b"\0")
            e["start"] = first
    mini_fat_bytes = struct.pack(f"<{len(mini_fat)}I", *mini_fat) if mini_fat else b""
    n_minifat = -(-len(mini_fat_bytes) // SECTOR)
    big = [e for e in entries if e["type"] == 2 and len(e.get("data", b"")) >= CUTOFF]
    dir_sectors = -(-len(entries) * 128 // SECTOR)
    ms_sectors = -(-len(mini_stream) // SECTOR)
    needed = dir_sectors + n_minifat + ms_sectors + sum(-(-len(e["data"]) // SECTOR) for e in big)
    n_fat = 1
    while n_fat + needed > n_fat * (SECTOR // 4):
        n_fat += 1
    fat = [FREESECT] * (n_fat * (SECTOR // 4))
    for i in range(n_fat):
        fat[i] = FATSECT
    body = bytearray()
    nxt = n_fat

    def chain(count: int) -> int:
        """Allocate `count` consecutive sectors as one FAT chain; return the first."""
        nonlocal nxt
        first = nxt
        for i in range(count):
            fat[nxt + i] = nxt + i + 1 if i < count - 1 else ENDOFCHAIN
        nxt += count
        return first

    first_dir = chain(dir_sectors)
    first_minifat = chain(n_minifat) if n_minifat else ENDOFCHAIN
    body_minifat = mini_fat_bytes.ljust(n_minifat * SECTOR, b"\xff")
    root_start = chain(ms_sectors) if ms_sectors else ENDOFCHAIN
    body_ministream = bytes(mini_stream).ljust(ms_sectors * SECTOR, b"\0")
    big_bodies = bytearray()
    for e in big:
        count = -(-len(e["data"]) // SECTOR)
        e["start"] = chain(count)
        big_bodies += e["data"].ljust(count * SECTOR, b"\0")
    entries[0]["start"], entries[0]["size"] = root_start, len(mini_stream)
    for e in entries:
        e.setdefault("start", ENDOFCHAIN if e["type"] == 2 else 0)

    directory = bytearray()
    for e in entries:
        name = e["name"].encode("utf-16-le") + b"\0\0"
        directory += name.ljust(64, b"\0") + struct.pack("<HBB", len(name), e["type"], 1)
        directory += struct.pack("<III", e["left"], e["right"], e["child"]) + b"\0" * 16 + b"\0" * 4 + b"\0" * 16
        size = len(e.get("data", b"")) if e["type"] == 2 else e.get("size", 0)
        directory += struct.pack("<IQ", e["start"], size)
    directory = directory.ljust(dir_sectors * SECTOR, b"\0")
    # Unused directory slots must read as empty entries with NOSTREAM links.
    for off in range(len(entries) * 128, len(directory), 128):
        directory[off + 68: off + 80] = struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM)

    header = bytearray(SECTOR)
    header[0:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<HHHHH", header, 24, 0x003E, 0x0003, 0xFFFE, 9, 6)
    struct.pack_into("<IIII", header, 40, 0, n_fat, first_dir, 0)
    struct.pack_into("<IIIII", header, 56, CUTOFF, first_minifat, n_minifat, ENDOFCHAIN, 0)
    difat = list(range(n_fat)) + [FREESECT] * (109 - n_fat)
    struct.pack_into("<109I", header, 76, *difat)
    fat_bytes = struct.pack(f"<{len(fat)}I", *fat)
    # Sector order matches the allocation order above: FAT, directory, mini FAT, mini stream, big streams.
    return bytes(header) + fat_bytes + bytes(directory) + body_minifat + body_ministream + bytes(big_bodies)
