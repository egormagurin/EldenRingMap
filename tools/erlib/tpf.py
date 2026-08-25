"""TPF reader - FromSoftware's texture container.

A TPF holds one or more DDS textures. The map tiles are single-texture TPFs; the
menu sheets hold 56, which is why this exists as a proper reader rather than the
"just take the first one" shortcut in extract_tiles.py.

Layout (little-endian):

    0x00  char[4] "TPF\\0"
    0x04  int32   dataSize
    0x08  int32   fileCount
    0x0C  byte    platform      (0 = PC)
    0x0D  byte    flag2         (3)
    0x0E  byte    encoding      (1 -> texture names are UTF-16LE)
    0x0F  byte    0
    0x10  entry[fileCount], stride 20:
            +0x00 int32 fileOffset
            +0x04 int32 fileSize
            +0x08 byte  format
            +0x09 byte  type
            +0x0A byte  mipmaps
            +0x0B byte  flags1
            +0x0C int32 nameOffset
            +0x10 int32 hasFloatStruct

The stride is 20 and the names are UTF-16, not the 0x24/ASCII shape used by some
other FromSoft titles - assuming otherwise yields entries that look plausible
but decode to garbage.
"""
import struct


class Texture:
    __slots__ = ("index", "name", "offset", "size", "format", "mipmaps", "flags")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"<Texture {self.name!r} {self.size:,}B fmt={self.format}>"


def parse(data: bytes):
    if data[:4] != b"TPF\x00":
        raise ValueError(f"not a TPF (magic {data[:4]!r})")
    count = struct.unpack_from("<i", data, 8)[0]
    encoding = data[0x0E]

    def name_at(off):
        if not (0 < off < len(data)):
            return ""
        if encoding == 1:                       # UTF-16LE
            end = off
            while end + 1 < len(data) and data[end:end + 2] != b"\x00\x00":
                end += 2
            return data[off:end].decode("utf-16-le", "replace")
        end = data.index(b"\x00", off)
        return data[off:end].decode("shift_jis", "replace")

    out = []
    for i in range(count):
        e = 0x10 + i * 20
        file_offset, file_size = struct.unpack_from("<ii", data, e)
        fmt, ttype, mips, flags1 = data[e + 8], data[e + 9], data[e + 10], data[e + 11]
        name_offset = struct.unpack_from("<i", data, e + 0x0C)[0]
        out.append(Texture(index=i, name=name_at(name_offset), offset=file_offset,
                           size=file_size, format=fmt, mipmaps=mips, flags=flags1))
    return out


def dds_to_rgba(dds: bytes):
    """DDS bytes -> (PIL.Image RGBA, width, height)."""
    from PIL import Image
    import texture2ddecoder

    if dds[:4] != b"DDS ":
        raise ValueError("not a DDS")
    height = struct.unpack_from("<I", dds, 12)[0]
    width = struct.unpack_from("<I", dds, 16)[0]
    fourcc = dds[84:88]

    if fourcc == b"DX10":
        dxgi = struct.unpack_from("<I", dds, 128)[0]
        payload = dds[148:]                    # DDS header + DX10 header
        codec = {98: "bc7", 99: "bc7", 71: "bc1", 72: "bc1",
                 77: "bc3", 78: "bc3", 80: "bc4", 83: "bc5"}.get(dxgi)
        if codec is None:
            raise ValueError(f"unsupported DXGI format {dxgi}")
    else:
        payload = dds[128:]
        codec = {b"DXT1": "bc1", b"DXT5": "bc3", b"DXT4": "bc3",
                 b"ATI1": "bc4", b"BC4U": "bc4",
                 b"ATI2": "bc5", b"BC5U": "bc5"}.get(fourcc)
        if codec is None:
            raise ValueError(f"unsupported DDS fourCC {fourcc!r}")

    raw = getattr(texture2ddecoder, f"decode_{codec}")(payload, width, height)
    return Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA"), width, height


def texture_image(tpf_bytes: bytes, tex: Texture):
    return dds_to_rgba(tpf_bytes[tex.offset:tex.offset + tex.size])
