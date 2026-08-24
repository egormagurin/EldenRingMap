"""Extract Elden Ring's world-map tiles from your own game install and build a
web tile pyramid.

Pipeline per tile:
    Data0.bdt  ->  71_maptile.tpfbdt  ->  DCX/Oodle  ->  TPF  ->  DDS(BC7)
               ->  RGBA  ->  stitched 10496x10496 master  ->  {z}/{x}/{y}.webp

Nothing is downloaded and nothing is redistributed: the tiles come from the copy
of the game on this machine and are written under web/tiles/, which is gitignored.

    python tools/extract_tiles.py                     # all four masters
    python tools/extract_tiles.py --masters M00       # just the Lands Between
    python tools/extract_tiles.py --keep-master       # also keep the giant PNG
"""
import argparse
import io
import json
import os
import re
import struct
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image
import texture2ddecoder

from erlib.dvdbnd import DvdBnd
from erlib import dcx, oodle, maptile_mask
from erlib.gamepath import require_game_dir

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TILE = 256
GRID = 41                       # 41 x 41 cells at LOD 0
MASTER_PX = GRID * TILE         # 10496
EVENT_BIT = 0x4000              # crater / Farum event layer - never want it

NAME_RE = re.compile(r"MENU_MapTile_(M\d{2})_L(\d)_(\d+)_(\d+)_([0-9A-Fa-f]{8})", re.I)

MASTER_LABELS = {
    "M00": "The Lands Between",
    "M01": "Underground",
    "M10": "Realm of Shadow (SOTE)",
    "M11": "Realm of Shadow - Underground",
}


# --------------------------------------------------------------------- formats

def parse_bhf4(data):
    """BHF4 = a BND4 directory whose payload lives in a separate .bdt slab."""
    assert data[:4] == b"BHF4", data[:4]
    count = struct.unpack_from("<I", data, 0x0C)[0]
    hdr_size = struct.unpack_from("<Q", data, 0x20)[0]
    out = []
    off = 0x40
    for _ in range(count):
        size = struct.unpack_from("<q", data, off + 0x08)[0]
        data_offset = struct.unpack_from("<I", data, off + 0x18)[0]
        name_off = struct.unpack_from("<I", data, off + 0x20)[0]
        end = name_off
        while data[end:end + 2] != b"\x00\x00":
            end += 2
        out.append((data[name_off:end].decode("utf-16-le", "replace"), data_offset, size))
        off += hdr_size
    return out


def tpf_to_rgba(tpf: bytes):
    """First texture of a TPF -> (PIL.Image RGBA, width, height)."""
    assert tpf[:4] == b"TPF\x00", tpf[:4]
    data_off, data_size = struct.unpack_from("<ii", tpf, 0x10)
    dds = tpf[data_off:data_off + data_size]
    if dds[:4] != b"DDS ":
        raise ValueError("texture is not a DDS")

    height = struct.unpack_from("<I", dds, 12)[0]
    width = struct.unpack_from("<I", dds, 16)[0]
    fourcc = dds[84:88]

    if fourcc == b"DX10":
        # DXT10 extension header sits between the DDS header and the payload.
        dxgi = struct.unpack_from("<I", dds, 128)[0]
        payload = dds[148:]
        codec = {98: "bc7", 99: "bc7", 71: "bc1", 72: "bc1",
                 77: "bc3", 78: "bc3", 80: "bc4", 83: "bc5"}.get(dxgi)
        if codec is None:
            raise ValueError(f"unsupported DXGI format {dxgi}")
    else:
        # Classic fourCC. Most of the map is BC7, but ~5% of cells still ship
        # as plain DXT1.
        payload = dds[128:]
        codec = {b"DXT1": "bc1", b"DXT5": "bc3", b"DXT4": "bc3",
                 b"ATI1": "bc4", b"BC4U": "bc4",
                 b"ATI2": "bc5", b"BC5U": "bc5"}.get(fourcc)
        if codec is None:
            raise ValueError(f"unsupported DDS fourCC {fourcc!r}")

    raw = getattr(texture2ddecoder, f"decode_{codec}")(payload, width, height)
    # texture2ddecoder returns BGRA
    return Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA"), width, height


def pick_variant(codes, mask=None):
    """Fully-revealed variant for a cell (see erlib.maptile_mask)."""
    return maptile_mask.choose_variant(codes, mask)


# --------------------------------------------------------------------- pyramid

def write_pyramid(master: Image.Image, out_dir: str, fmt: str, quality: int):
    """Emit {z}/{x}/{y}.<fmt> for z = 0..native, skipping fully transparent tiles."""
    native = 0
    while TILE * (2 ** native) < max(master.size):
        native += 1                                   # ceil(log2(size/TILE)) -> 6

    written, skipped = 0, 0
    index = {}
    for z in range(native, -1, -1):
        scale = 2 ** (native - z)
        w = max(1, master.width // scale)
        h = max(1, master.height // scale)
        img = master if scale == 1 else master.resize((w, h), Image.LANCZOS)
        cols = (w + TILE - 1) // TILE
        rows = (h + TILE - 1) // TILE
        present = []
        for x in range(cols):
            for y in range(rows):
                box = (x * TILE, y * TILE, min((x + 1) * TILE, w), min((y + 1) * TILE, h))
                cell = img.crop(box)
                if cell.size != (TILE, TILE):         # pad edge tiles
                    padded = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
                    padded.paste(cell, (0, 0))
                    cell = padded
                if not cell.getbbox():                # fully transparent
                    skipped += 1
                    continue
                d = os.path.join(out_dir, str(z), str(x))
                os.makedirs(d, exist_ok=True)
                path = os.path.join(d, f"{y}.{fmt}")
                if fmt == "webp":
                    cell.save(path, "WEBP", quality=quality, alpha_quality=100, method=4)
                else:
                    cell.save(path, "PNG", optimize=True)
                present.append([x, y])
                written += 1
        index[z] = present
        if img is not master:
            img.close()
    return native, written, skipped, index


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game-dir", default=None,
                    help="the ...\\ELDEN RING\\Game folder (auto-detected if omitted)")
    ap.add_argument("--out", default=os.path.join(ROOT, "web", "tiles"))
    ap.add_argument("--masters", default="M00,M01,M10,M11")
    ap.add_argument("--lod", type=int, default=0, help="0 = highest detail")
    ap.add_argument("--format", default="webp", choices=["webp", "png"])
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--keep-master", action="store_true",
                    help="also write the stitched 10496x10496 PNG")
    args = ap.parse_args()

    args.game_dir = require_game_dir(args.game_dir)

    cache = os.path.join(ROOT, "cache")
    os.makedirs(cache, exist_ok=True)
    os.makedirs(args.out, exist_ok=True)

    print(f"opening archives in {args.game_dir}")
    t0 = time.time()
    dvd = DvdBnd(args.game_dir, cache_dir=cache)
    bdt_entry = dvd.entry("/menu/71_maptile.tpfbdt")
    if bdt_entry is None:
        sys.exit("could not find /menu/71_maptile.tpfbdt - is --game-dir correct?")

    hdr_path = os.path.join(cache, "71_maptile.tpfbhd")
    if not os.path.exists(hdr_path):
        with open(hdr_path, "wb") as f:
            f.write(dvd.read("/menu/71_maptile.tpfbhd"))
    entries = parse_bhf4(open(hdr_path, "rb").read())
    print(f"  tile index: {len(entries):,} textures ({time.time() - t0:.1f}s)")

    # group: master -> lod -> (col,row) -> {code: (offset,size)}
    grouped = {}
    for name, off, size in entries:
        m = NAME_RE.search(name)
        if not m:
            continue
        master, lod, col, row, code = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
        grouped.setdefault(master, {}).setdefault(lod, {}).setdefault((col, row), {})[code] = (off, size)

    helper = oodle.make_helper(args.game_dir)
    msk_path = os.path.join(cache, "71_maptile.mtmskbnd.dcx")
    if not os.path.exists(msk_path):
        with open(msk_path, "wb") as f:
            f.write(dvd.read("/menu/71_maptile.mtmskbnd.dcx"))
    masks = maptile_mask.load_masks(open(msk_path, "rb").read(), oodle=helper)
    print("  reveal masks: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(masks.items())))

    bdt = dvd._bdt(bdt_entry.archive)
    manifest = {"tileSize": TILE, "grid": GRID, "masterPx": MASTER_PX,
                "format": args.format, "masters": {}}

    for master in args.masters.split(","):
        master = master.strip()
        cells = grouped.get(master, {}).get(args.lod)
        if not cells:
            print(f"\n{master}: no LOD{args.lod} tiles, skipping")
            continue

        print(f"\n=== {master} ({MASTER_LABELS.get(master, '')}) - {len(cells)} cells ===")
        canvas = Image.new("RGBA", (MASTER_PX, MASTER_PX), (0, 0, 0, 0))
        t1 = time.time()
        ok = fail = 0
        mask_table = masks.get(master, {})
        for i, ((col, row), variants) in enumerate(sorted(cells.items())):
            code = pick_variant(variants.keys(),
                                mask_table.get(maptile_mask.mask_id(args.lod, col, row)))
            off, size = variants[code]
            try:
                bdt.seek(bdt_entry.offset + off)
                raw = bdt.read(size)
                tpf = dcx.decompress(raw, oodle=helper)
                img, w, h = tpf_to_rgba(tpf)
                # filename row counts south->north; the canvas is north-up
                canvas.paste(img, (col * TILE, (GRID - 1 - row) * TILE))
                img.close()
                ok += 1
            except Exception as exc:
                fail += 1
                if fail <= 5:
                    print(f"    ! {master} L{args.lod} {col}_{row}_{code}: {exc}")
            if (i + 1) % 400 == 0:
                print(f"    {i + 1}/{len(cells)} cells  ({time.time() - t1:.0f}s)")
        print(f"  stitched {ok} tiles ({fail} failed) in {time.time() - t1:.0f}s")

        if args.keep_master:
            mp = os.path.join(cache, f"master_{master}.png")
            canvas.save(mp)
            print(f"  master image -> {mp}")

        out_dir = os.path.join(args.out, master)
        t2 = time.time()
        native, written, skipped, index = write_pyramid(canvas, out_dir, args.format, args.quality)
        print(f"  pyramid z0..z{native}: {written} tiles written, {skipped} blank skipped "
              f"({time.time() - t2:.0f}s)")
        canvas.close()

        manifest["masters"][master] = {
            "label": MASTER_LABELS.get(master, master),
            "nativeZoom": native,
            "width": MASTER_PX,
            "height": MASTER_PX,
            "tiles": {str(z): index[z] for z in index},
        }

    dvd.close()
    mf = os.path.join(args.out, "manifest.json")
    with open(mf, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    print(f"\nmanifest -> {mf}")
    print(f"total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
