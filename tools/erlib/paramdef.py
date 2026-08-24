"""PARAMDEF reader - gives PARAM row bytes their field names.

A PARAMDEF is an XML list of `<Field Def="u32 eventflagId"/>` declarations.
Rows are packed in declaration order with NO automatic alignment; the defs
include explicit `dummy8` padding fields wherever alignment is needed.
Consecutive bitfields (`name:3`) share one storage unit of their base type.
"""
import re
import struct
import xml.etree.ElementTree as ET

# name -> (struct code, size in bytes)
TYPES = {
    "s8": ("b", 1), "u8": ("B", 1), "dummy8": ("B", 1),
    "s16": ("h", 2), "u16": ("H", 2),
    "s32": ("i", 4), "u32": ("I", 4), "b32": ("i", 4),
    "f32": ("f", 4), "angle32": ("f", 4),
    "f64": ("d", 8),
}

_DEF_RE = re.compile(
    r"^\s*(?P<type>\w+)\s+(?P<name>\w+)"
    r"(?:\s*\[\s*(?P<count>\d+)\s*\])?"
    r"(?:\s*:\s*(?P<bits>\d+))?"
    r"(?:\s*=\s*(?P<default>\S+))?\s*$"
)


class Field:
    __slots__ = ("name", "type", "code", "size", "count", "bits", "offset", "bit_offset")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __repr__(self):
        b = f":{self.bits}@{self.bit_offset}" if self.bits else ""
        c = f"[{self.count}]" if self.count > 1 else ""
        return f"<{self.type} {self.name}{c}{b} @0x{self.offset:x}>"


class ParamDef:
    def __init__(self, xml_text: str):
        root = ET.fromstring(xml_text)
        self.param_type = (root.findtext("ParamType") or "").strip()
        self.data_version = int(root.findtext("DataVersion") or 0)

        self.fields = []
        self.by_name = {}
        offset = 0
        # `dummy8` is padding but packs into the same bitfield unit as `u8`, so
        # the unit is keyed by (struct code, size) rather than by type name.
        bit_unit = None
        bit_used = 0

        for fe in root.find("Fields"):
            m = _DEF_RE.match(fe.get("Def", ""))
            if not m:
                continue
            tname = m.group("type")
            if tname.startswith("fixstr"):
                # fixstr name[n] / fixstrW name[n]: raw byte blob
                count = int(m.group("count") or 1)
                size = count * (2 if tname == "fixstrW" else 1)
                if bit_unit:
                    offset += bit_unit[1]
                    bit_unit, bit_used = None, 0
                f = Field(name=m.group("name"), type=tname, code=None, size=size,
                          count=1, bits=0, offset=offset, bit_offset=0)
                offset += size
            else:
                if tname not in TYPES:
                    continue
                code, size = TYPES[tname]
                count = int(m.group("count") or 1)
                bits = int(m.group("bits") or 0)

                unit = (code.upper(), size)
                if bits:
                    if bit_unit != unit or bit_used + bits > size * 8:
                        if bit_unit:
                            offset += bit_unit[1]
                        bit_unit, bit_used = unit, 0
                    f = Field(name=m.group("name"), type=tname, code=code, size=size,
                              count=1, bits=bits, offset=offset, bit_offset=bit_used)
                    bit_used += bits
                else:
                    if bit_unit:
                        offset += bit_unit[1]
                        bit_unit, bit_used = None, 0
                    f = Field(name=m.group("name"), type=tname, code=code, size=size,
                              count=count, bits=0, offset=offset, bit_offset=0)
                    offset += size * count

            self.fields.append(f)
            self.by_name.setdefault(f.name, f)

        if bit_unit:
            offset += bit_unit[1]
        self.row_size = offset

    # ------------------------------------------------------------------ access

    def get(self, row_bytes: bytes, name: str):
        f = self.by_name.get(name)
        if f is None:
            raise KeyError(name)
        if f.code is None:
            return row_bytes[f.offset:f.offset + f.size]
        if f.bits:
            raw = struct.unpack_from("<" + f.code.upper(), row_bytes, f.offset)[0]
            return (raw >> f.bit_offset) & ((1 << f.bits) - 1)
        if f.count > 1:
            return struct.unpack_from("<" + f.code * f.count, row_bytes, f.offset)
        return struct.unpack_from("<" + f.code, row_bytes, f.offset)[0]

    def as_dict(self, row_bytes: bytes, names=None):
        out = {}
        for n in (names or self.by_name):
            try:
                out[n] = self.get(row_bytes, n)
            except Exception:
                pass
        return out


def load(path: str) -> ParamDef:
    with open(path, encoding="utf-8-sig") as f:
        return ParamDef(f.read())
