"""Parse 71_maptile.tpfbhd and summarise the map tile inventory.

Tile names look like:  MENU_MapTile_M00_L0_17_23_0004a1ff.tpf.dcx
    M00 = Lands Between surface   M01 = underground
    M10 = Shadow of the Erdtree   M11 = DLC underground
    L0  = highest detail LOD
    _CC_ = column (west->east)    _RR_ = row (south->north, needs Y flip)
    trailing hex = variant bitmask (which map fragments are collected)
"""
import sys
import os
import re
import struct
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cache")
HDR = os.path.join(CACHE, "71_maptile.tpfbhd")

NAME_RE = re.compile(
    r"MENU_MapTile_(M\d{2})_L(\d)_(\d+)_(\d+)_([0-9A-Fa-f]{8})", re.I)


def parse_bhf4(data):
    """BHF4 = BND4 directory whose payload lives in a separate .bdt slab."""
    assert data[:4] == b"BHF4", data[:4]
    file_count = struct.unpack_from("<I", data, 0x0C)[0]
    file_header_size = struct.unpack_from("<Q", data, 0x20)[0]
    unicode_flag = data[0x30] != 0
    fmt = data[0x31]
    entries = []
    off = 0x40
    for i in range(file_count):
        size = struct.unpack_from("<q", data, off + 0x08)[0]
        uncompressed = struct.unpack_from("<q", data, off + 0x10)[0]
        data_offset = struct.unpack_from("<I", data, off + 0x18)[0]
        ent_id = struct.unpack_from("<i", data, off + 0x1C)[0]
        name_off = struct.unpack_from("<I", data, off + 0x20)[0]
        end = name_off
        while data[end:end + 2] != b"\x00\x00":
            end += 2
        name = data[name_off:end].decode("utf-16-le", "replace")
        entries.append(dict(name=name, size=size, uncompressed=uncompressed,
                            offset=data_offset, id=ent_id))
        off += file_header_size
    return entries, dict(file_count=file_count, file_header_size=file_header_size,
                         unicode=unicode_flag, format=hex(fmt))


def main():
    with open(HDR, "rb") as f:
        data = f.read()
    entries, meta = parse_bhf4(data)
    print(f"BHF4: {meta}")
    print(f"entries: {len(entries):,}")
    print(f"sample names:")
    for e in entries[:5]:
        print(f"    {e['name']}   size={e['size']:,} off={e['offset']:,}")

    maps = defaultdict(lambda: defaultdict(list))
    unmatched = 0
    for e in entries:
        m = NAME_RE.search(e["name"])
        if not m:
            unmatched += 1
            continue
        master, lod, col, row, code = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
        maps[master][lod].append((col, row, code, e))

    print(f"\nunmatched names: {unmatched}")
    print(f"\n{'master':<8}{'LOD':<6}{'tiles':>8}  {'cols':<12}{'rows':<12}variants")
    for master in sorted(maps):
        for lod in sorted(maps[master]):
            tiles = maps[master][lod]
            cols = [t[0] for t in tiles]
            rows = [t[1] for t in tiles]
            cells = len({(t[0], t[1]) for t in tiles})
            print(f"{master:<8}{'L'+str(lod):<6}{len(tiles):>8}  "
                  f"{min(cols)}-{max(cols):<9}{min(rows)}-{max(rows):<9}"
                  f"cells={cells} avgVariants={len(tiles)/max(cells,1):.1f}")

    print("\n=== DLC VERDICT ===")
    for m in ("M00", "M01", "M10", "M11"):
        n = sum(len(v) for v in maps.get(m, {}).values())
        print(f"  {m}: {n:,} tile textures {'<-- present' if n else '<-- ABSENT'}")

    l0 = maps.get("M00", {}).get(0, [])
    if l0:
        codes = Counter(t[2] for t in l0)
        print(f"\nM00 L0 variant codes (top 10 of {len(codes)}):")
        for c, n in codes.most_common(10):
            print(f"    {c}  x{n}")


if __name__ == "__main__":
    main()
