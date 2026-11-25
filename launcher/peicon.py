"""The application icon stored inside a Windows executable (PE file).

Reads only what it needs — the headers and the resource section — through a
`read_at(offset, size)` function, so the same code works on a local file and
on a release asset fetched with HTTP range requests (a few hundred KB instead
of the whole .exe).

The icon returned is the largest image of the first icon group (the one
Explorer shows): PNG bytes as they are, or a single-image .ico otherwise.
No Qt here.
"""

from __future__ import annotations

import struct
from pathlib import Path

RT_ICON = 3
RT_GROUP_ICON = 14
MAX_RESOURCE_SECTION = 16 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IconError(ValueError):
    """The file is not a PE executable or has no usable icon."""


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _resource_section(read_at):
    """(section bytes, section RVA) of the resource table."""
    dos = read_at(0, 64)
    if len(dos) < 64 or dos[:2] != b"MZ":
        raise IconError("not an executable")
    pe_offset = _u32(dos, 0x3C)
    if not 0 < pe_offset < 64 * 1024:
        raise IconError("bad PE offset")
    head = read_at(pe_offset, 24 + 240)
    if head[:4] != b"PE\0\0":
        raise IconError("no PE signature")
    sections = _u16(head, 6)
    optional_size = _u16(head, 20)
    optional = read_at(pe_offset + 24, optional_size)
    magic = _u16(optional, 0)
    if magic == 0x20B:                       # PE32+
        count_at, dirs_at = 108, 112
    elif magic == 0x10B:                     # PE32
        count_at, dirs_at = 92, 96
    else:
        raise IconError("unknown optional header")
    if _u32(optional, count_at) <= 2:
        raise IconError("no resource directory")
    rsrc_rva, rsrc_size = struct.unpack_from("<II", optional, dirs_at + 2 * 8)
    if not rsrc_rva or not rsrc_size:
        raise IconError("no resources")
    table = read_at(pe_offset + 24 + optional_size, sections * 40)
    for i in range(sections):
        _, vsize, va, raw_size, raw_ptr = struct.unpack_from("<8sIIII", table, i * 40)
        if va <= rsrc_rva < va + max(vsize, raw_size):
            size = min(max(raw_size, rsrc_size + (rsrc_rva - va)), MAX_RESOURCE_SECTION)
            data = read_at(raw_ptr, size)
            return data, va
    raise IconError("resource section not found")


def _entries(section: bytes, offset: int):
    """Entries of a resource directory: [(id or None, is_dir, offset)]."""
    named, ids = struct.unpack_from("<HH", section, offset + 12)
    out = []
    for i in range(named + ids):
        name, target = struct.unpack_from("<II", section, offset + 16 + i * 8)
        ident = None if name & 0x80000000 else name
        out.append((ident, bool(target & 0x80000000), target & 0x7FFFFFFF))
    return out


def _first_data(section: bytes, offset: int, va: int) -> bytes:
    """Data of the first leaf under a directory (any language)."""
    for _, is_dir, target in _entries(section, offset):
        if is_dir:
            return _first_data(section, target, va)
        rva, size = struct.unpack_from("<II", section, target)
        start = rva - va
        if 0 <= start and start + size <= len(section):
            return section[start:start + size]
    raise IconError("empty resource")


def _by_id(section: bytes, offset: int, va: int) -> dict:
    """{id: data} of every resource of one type."""
    out = {}
    for ident, is_dir, target in _entries(section, offset):
        if ident is None:
            continue
        try:
            out[ident] = _first_data(section, target, va) if is_dir else None
        except (IconError, struct.error):
            continue
    return out


def extract(read_at) -> tuple[bytes, str]:
    """(image bytes, 'png' | 'ico') of the executable's main icon."""
    try:
        section, va = _resource_section(read_at)
        types = {ident: target for ident, is_dir, target in _entries(section, 0) if is_dir}
        if RT_GROUP_ICON not in types or RT_ICON not in types:
            raise IconError("no icon")
        groups = [target for _, is_dir, target in _entries(section, types[RT_GROUP_ICON]) if is_dir]
        if not groups:
            raise IconError("no icon group")
        group = _first_data(section, groups[0], va)
        images = _by_id(section, types[RT_ICON], va)
    except struct.error as exc:
        raise IconError(f"truncated resources: {exc}") from None

    count = _u16(group, 4)
    best = None
    for i in range(count):
        width, height, colors, _, planes, bits, size, ident = struct.unpack_from("<BBBBHHIH", group, 6 + i * 14)
        data = images.get(ident)
        if not data:
            continue
        score = ((width or 256) * (height or 256), bits)
        if best is None or score > best[0]:
            best = (score, (width, height, colors, planes, bits), data)
    if best is None:
        raise IconError("icon images missing")
    _, (width, height, colors, planes, bits), data = best
    if data.startswith(PNG_SIGNATURE):
        return data, "png"
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", width, height, colors, 0, planes, bits, len(data), 6 + 16)
    return header + entry + data, "ico"


def file_reader(path: Path):
    """read_at() for a local file."""
    handle = open(path, "rb")

    def read_at(offset: int, size: int) -> bytes:
        handle.seek(offset)
        return handle.read(size)

    read_at.close = handle.close
    return read_at


def extract_from_file(path: Path) -> tuple[bytes, str]:
    reader = file_reader(Path(path))
    try:
        return extract(reader)
    finally:
        reader.close()
