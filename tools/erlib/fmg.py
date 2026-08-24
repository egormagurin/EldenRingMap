"""FMG reader - FromSoftware's localized string tables.

An FMG maps integer text ids to UTF-16 strings. Elden Ring uses version 2 with
64-bit offsets. Ids are stored as ranges ("groups") pointing into a flat table of
string offsets, which keeps sparse id spaces compact.
"""
import struct


def parse(data: bytes) -> dict:
    """-> {id: string}. Entries with a null offset are absent strings."""
    if len(data) < 0x30:
        raise ValueError("FMG too small")
    version = data[2]
    big_endian = data[1] != 0
    if big_endian:
        raise ValueError("big-endian FMG not supported")

    wide = version == 2
    group_count = struct.unpack_from("<i", data, 0x0C)[0]
    string_count = struct.unpack_from("<i", data, 0x10)[0]

    if wide:
        string_offsets_offset = struct.unpack_from("<q", data, 0x18)[0]
        groups_at = 0x28
        group_size = 16
    else:
        string_offsets_offset = struct.unpack_from("<i", data, 0x18)[0]
        groups_at = 0x1C
        group_size = 12

    out = {}
    p = groups_at
    for _ in range(group_count):
        offset_index, first_id, last_id = struct.unpack_from("<iii", data, p)
        p += group_size
        for i, sid in enumerate(range(first_id, last_id + 1)):
            idx = offset_index + i
            if idx >= string_count:
                continue
            if wide:
                so = struct.unpack_from("<q", data, string_offsets_offset + idx * 8)[0]
            else:
                so = struct.unpack_from("<i", data, string_offsets_offset + idx * 4)[0]
            if not so:
                continue
            end = so
            while end + 1 < len(data) and data[end:end + 2] != b"\x00\x00":
                end += 2
            out[sid] = data[so:end].decode("utf-16-le", "replace")
    return out


def load_msgbnd(msgbnd_bytes: bytes, oodle=None) -> dict:
    """A .msgbnd.dcx -> {fmgName: {id: string}}."""
    from . import dcx, bnd4
    b = bnd4.BND4(dcx.decompress(msgbnd_bytes, oodle=oodle))
    out = {}
    for e in b.entries:
        name = e.name.replace(chr(92), "/").split("/")[-1]
        if not name.lower().endswith(".fmg"):
            continue
        try:
            out[name[:-4]] = parse(b.read(e))
        except Exception:
            out[name[:-4]] = {}
    return out
