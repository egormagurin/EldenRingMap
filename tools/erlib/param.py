"""FromSoftware PARAM reader (Elden Ring flavour).

A PARAM is a table: a header, a row index (id -> data offset), packed row data of
uniform size, and a UTF-16 string blob. The *meaning* of the bytes in a row comes
from a separate paramdef; this reader deliberately does not require one. It gives
you row ids and raw row bytes, and `defs.py` layers field names on top when a def
is available.
"""
import struct


class Row:
    __slots__ = ("id", "name", "data")

    def __init__(self, id, name, data):
        self.id = id
        self.name = name
        self.data = data

    def __repr__(self):
        return f"<Row {self.id} {self.name!r} {len(self.data)}B>"


class Param:
    def __init__(self, data: bytes, name: str = ""):
        self.raw = data
        self.name = name
        self.strings_offset = struct.unpack_from("<I", data, 0x00)[0]
        self.short_data_offset = struct.unpack_from("<H", data, 0x04)[0]
        self.unk06 = struct.unpack_from("<H", data, 0x06)[0]
        self.paramdef_data_version = struct.unpack_from("<H", data, 0x08)[0]
        self.row_count = struct.unpack_from("<H", data, 0x0A)[0]
        self.format2d = data[0x2D]
        self.format2e = data[0x2E]
        self.paramdef_format_version = data[0x2F]

        # Elden Ring uses 64-bit offsets ("long data offsets"), so the row index
        # entries are 24 bytes: id(4) pad(4) dataOffset(8) nameOffset(8).
        self.wide = bool(self.format2d & 0x04)
        self.param_type = self._read_param_type()
        self.rows = self._read_rows()

    def _read_param_type(self):
        if self.format2d & 0x80:
            # paramType lives at an offset stored at 0x38
            off = struct.unpack_from("<Q", self.raw, 0x38)[0]
            end = self.raw.index(b"\x00", off)
            return self.raw[off:end].decode("ascii", "replace")
        end = self.raw.index(b"\x00", 0x0C)
        return self.raw[0x0C:end].decode("ascii", "replace")

    def _read_rows(self):
        entry_size = 24 if self.wide else 12
        base = 0x40 if self.wide else 0x30
        index = []
        for i in range(self.row_count):
            o = base + i * entry_size
            if self.wide:
                rid = struct.unpack_from("<i", self.raw, o)[0]
                data_off = struct.unpack_from("<Q", self.raw, o + 8)[0]
                name_off = struct.unpack_from("<Q", self.raw, o + 16)[0]
            else:
                rid = struct.unpack_from("<i", self.raw, o)[0]
                data_off = struct.unpack_from("<I", self.raw, o + 4)[0]
                name_off = struct.unpack_from("<I", self.raw, o + 8)[0]
            index.append((rid, data_off, name_off))

        # Row size = gap between consecutive data offsets (rows are uniform).
        offs = sorted({d for _, d, _ in index})
        row_size = min((b - a for a, b in zip(offs, offs[1:])), default=0)

        rows = []
        for rid, data_off, name_off in index:
            rows.append(Row(rid, self._read_name(name_off), self.raw[data_off:data_off + row_size]))
        self.row_size = row_size
        return rows

    def _read_name(self, off):
        if not off or off >= len(self.raw):
            return ""
        end = off
        while end + 1 < len(self.raw) and self.raw[end:end + 2] != b"\x00\x00":
            end += 2
        try:
            return self.raw[off:end].decode("utf-16-le").strip("\x00")
        except UnicodeDecodeError:
            return ""

    def ids(self):
        return [r.id for r in self.rows]

    def by_id(self, rid):
        for r in self.rows:
            if r.id == rid:
                return r
        return None


def load_params(regulation_path):
    """Return {shortName: Param} for every param in a regulation.bin."""
    from . import regulation as _reg, bnd4 as _bnd4
    bnd = _bnd4.BND4(_reg.load(regulation_path))
    out = {}
    for e in bnd.entries:
        short = e.name.replace(chr(92), "/").split("/")[-1]
        short = short[:-6] if short.endswith(".param") else short
        try:
            out[short] = Param(bnd.read(e), short)
        except Exception as exc:  # a malformed param must not kill the whole load
            out[short] = None
            print(f"  ! failed to parse {short}: {exc}")
    return out
