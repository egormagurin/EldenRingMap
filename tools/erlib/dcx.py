"""DCX container reader (FromSoftware single-file compression wrapper).

Big-endian header. Supported payload codecs: ZSTD (Elden Ring 1.12+ regulation),
DFLT (zlib), KRAK (Oodle - needs the game's oo2core DLL).
"""
import struct
import zlib

def _u32be(b, o):
    return struct.unpack_from(">I", b, o)[0]

def is_dcx(data: bytes) -> bool:
    return data[:4] == b"DCX\x00"

def decompress(data: bytes, oodle=None) -> bytes:
    if not is_dcx(data):
        return data
    dcs_off = _u32be(data, 0x08)
    dcp_off = _u32be(data, 0x0C)
    assert data[dcs_off:dcs_off + 4] == b"DCS\x00", "bad DCS magic"
    uncompressed_size = _u32be(data, dcs_off + 4)
    compressed_size = _u32be(data, dcs_off + 8)
    assert data[dcp_off:dcp_off + 4] == b"DCP\x00", "bad DCP magic"
    fmt = data[dcp_off + 4:dcp_off + 8]

    # The payload starts right after the DCA chunk.
    dca_off = data.find(b"DCA\x00", dcp_off)
    assert dca_off != -1, "no DCA chunk"
    dca_size = _u32be(data, dca_off + 4)
    payload = data[dca_off + dca_size: dca_off + dca_size + compressed_size]

    if fmt == b"ZSTD":
        import zstandard
        out = zstandard.ZstdDecompressor().decompress(
            payload, max_output_size=max(uncompressed_size, 1) * 2)
    elif fmt == b"DFLT":
        out = zlib.decompress(payload)
    elif fmt == b"KRAK":
        if oodle is None:
            raise RuntimeError("KRAK (Oodle) payload needs the oodle helper")
        out = oodle(payload, uncompressed_size)
    else:
        raise RuntimeError(f"unsupported DCX codec {fmt!r}")

    if len(out) != uncompressed_size:
        out = out[:uncompressed_size]
    return out

def info(data: bytes) -> dict:
    dcs_off = _u32be(data, 0x08)
    dcp_off = _u32be(data, 0x0C)
    return {
        "codec": data[dcp_off + 4:dcp_off + 8].decode("latin1"),
        "uncompressed": _u32be(data, dcs_off + 4),
        "compressed": _u32be(data, dcs_off + 8),
    }
