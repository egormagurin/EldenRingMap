"""Generic BND4 reader (game archives, e.g. the BND4 inside regulation.bin).

This is the *game* flavour of BND4, which differs from the save-file flavour:
entries carry names, ids and optional per-entry DCX compression.
"""
import struct
from . import dcx

class Entry:
    __slots__ = ("index", "name", "id", "data_offset", "size", "uncompressed_size", "flags")
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
    def __repr__(self):
        return f"<Entry {self.name!r} id={self.id} size={self.size}>"

class BND4:
    def __init__(self, data: bytes):
        assert data[:4] == b"BND4", "not a BND4"
        self.data = data
        self.file_count = struct.unpack_from("<I", data, 0x0C)[0]
        self.version = data[0x18:0x20].decode("latin1").rstrip("\x00")
        self.file_header_size = struct.unpack_from("<Q", data, 0x20)[0]
        self.unicode = data[0x30] != 0
        self.format = data[0x31]
        self.entries = []

        off = 0x40
        for i in range(self.file_count):
            flags = data[off]
            compressed_size = struct.unpack_from("<q", data, off + 0x08)[0]
            uncompressed_size = struct.unpack_from("<q", data, off + 0x10)[0]
            data_offset = struct.unpack_from("<I", data, off + 0x18)[0]
            ent_id = struct.unpack_from("<i", data, off + 0x1C)[0]
            name_offset = struct.unpack_from("<I", data, off + 0x20)[0]
            name = self._read_name(name_offset)
            self.entries.append(Entry(index=i, name=name, id=ent_id,
                                      data_offset=data_offset, size=compressed_size,
                                      uncompressed_size=uncompressed_size, flags=flags))
            off += self.file_header_size

    def _read_name(self, off):
        if off <= 0 or off >= len(self.data):
            return ""
        if self.unicode:
            end = off
            while end + 1 < len(self.data) and self.data[end:end + 2] != b"\x00\x00":
                end += 2
            return self.data[off:end].decode("utf-16-le", "replace")
        end = self.data.index(b"\x00", off)
        return self.data[off:end].decode("shift_jis", "replace")

    def read(self, entry: Entry) -> bytes:
        raw = self.data[entry.data_offset: entry.data_offset + entry.size]
        if dcx.is_dcx(raw):
            raw = dcx.decompress(raw)
        return raw

    def by_name(self, needle: str):
        n = needle.lower()
        return [e for e in self.entries if n in e.name.lower()]
