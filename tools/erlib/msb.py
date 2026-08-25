"""MSB reader - FromSoftware's map layout format (Elden Ring flavour, "MSBE").

An MSB describes everything placed in one map: models, parts (the actual objects
in the world, with positions), regions, routes, layers and events. We only need
two of those lists - PARTS for positions, EVENTS for treasure/item-lot links -
so this reader walks the container generically and decodes entry internals
lazily.

File layout (little-endian, 64-bit offsets anchored at file start):

    0x00  "MSB "
    0x04  int32  version        (1)
    0x08  int32  headerSize     (0x10)
    0x0C  byte   bigEndian
    0x0D  byte   bitBigEndian
    0x0E  byte   unk0E
    0x0F  byte   unk0F

then one "param list" per section, back to back:

    +0x00  int32  version
    +0x04  int32  offsetCount        (= entryCount + 2: name + entries + next)
    +0x08  int64  nameOffset         -> UTF-16LE list name, e.g. "PARTS_PARAM_ST"
    +0x10  int64  entryOffsets[offsetCount - 1]
           int64  nextListOffset     (0 on the last list)

Verified against m60_42_36_00.msb from a real install: the first list declares
offsetCount 97, its 96 entry offsets run 0x20..0x320, nextListOffset sits at
0x320, and the list name string begins at 0x328 - exactly where this layout
predicts.
"""
import struct


class ParamList:
    __slots__ = ("name", "version", "entry_offsets", "next_offset")

    def __init__(self, name, version, entry_offsets, next_offset):
        self.name = name
        self.version = version
        self.entry_offsets = entry_offsets
        self.next_offset = next_offset

    def __repr__(self):
        return f"<{self.name} {len(self.entry_offsets)} entries>"


class MSB:
    def __init__(self, data: bytes):
        if data[:4] != b"MSB ":
            raise ValueError(f"not an MSB (magic {data[:4]!r})")
        self.data = data
        self.version = struct.unpack_from("<i", data, 4)[0]
        header_size = struct.unpack_from("<i", data, 8)[0]
        self.big_endian = data[0x0C] != 0
        if self.big_endian:
            raise ValueError("big-endian MSB not supported")

        self.lists = {}
        self.order = []
        p = header_size
        seen = set()
        while p and p < len(data) and p not in seen:
            seen.add(p)
            lst = self._read_list(p)
            self.lists[lst.name] = lst
            self.order.append(lst.name)
            p = lst.next_offset

    def _read_list(self, p):
        version = struct.unpack_from("<i", self.data, p)[0]
        offset_count = struct.unpack_from("<i", self.data, p + 4)[0]
        name_offset = struct.unpack_from("<q", self.data, p + 8)[0]
        n = max(0, offset_count - 1)
        entry_offsets = list(struct.unpack_from(f"<{n}q", self.data, p + 0x10))
        next_offset = struct.unpack_from("<q", self.data, p + 0x10 + n * 8)[0]
        return ParamList(self._utf16(name_offset), version, entry_offsets, next_offset)

    def _utf16(self, off):
        if not off or off >= len(self.data):
            return ""
        end = off
        while end + 1 < len(self.data) and self.data[end:end + 2] != b"\x00\x00":
            end += 2
        return self.data[off:end].decode("utf-16-le", "replace")

    # ------------------------------------------------------------------ access

    def list_names(self):
        return list(self.order)

    def entries(self, list_name):
        """-> [(entryOffset, entryName)] for one list."""
        lst = self.lists.get(list_name)
        if not lst:
            return []
        out = []
        for off in lst.entry_offsets:
            if off <= 0 or off >= len(self.data):
                continue
            name_off = struct.unpack_from("<q", self.data, off)[0]
            out.append((off, self._utf16(off + name_off) if name_off else ""))
        return out

    def u8(self, o):   return self.data[o]
    def i32(self, o):  return struct.unpack_from("<i", self.data, o)[0]
    def u32(self, o):  return struct.unpack_from("<I", self.data, o)[0]
    def i64(self, o):  return struct.unpack_from("<q", self.data, o)[0]
    def f32(self, o):  return struct.unpack_from("<f", self.data, o)[0]
    def vec3(self, o): return struct.unpack_from("<3f", self.data, o)


def load(msb_bytes):
    return MSB(msb_bytes)
