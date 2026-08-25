"""Extract the game's own world-map icon sprites.

The map screen labels a lot of places with an icon and no text - grace rays,
rebirth monuments, NPC markers. Those markers exist in our dataset but had
nothing to draw except a coloured dot. This pulls the real sprites out.

    /menu/hi/01_common.tpf.dcx       -> 56 textures; 3 are the map-cursor sheets
    /menu/hi/01_common.sblytbnd.dcx  -> BND4 of .layout XML atlases giving the
                                        sub-rectangle of every sprite

    python tools/extract_icons.py    -> web/icons/*.png + data/map-icons.json

Output lands under web/ so the existing static handler serves it. Like the map
tiles, these are FromSoftware assets: extracted locally, never committed.
"""
import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

from erlib import dcx, oodle, bnd4, param, paramdef, tpf as tpflib
from erlib.dvdbnd import DvdBnd
from erlib.gamepath import require_game_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFS = os.path.join(ROOT, "data", "paramdefs")

TPF_PATH = "/menu/hi/01_common.tpf.dcx"
LAYOUT_PATH = "/menu/hi/01_common.sblytbnd.dcx"
SHEETS = ("SB_MapCursor", "SB_MapCursor_02", "SB_MapCursor_03_dlc")

# iconId -> sprite name. Everything else is MENU_MAP_%02d.
SPRITE_EXCEPTIONS = {
    1: "MENU_MAP_01_Bonfire",     # Sites of Grace
    3: "MENU_MAP_Church",
}
NO_SPRITE = {0, 15}               # 0 = no icon at all; 15 (River Well) has none

MAX_HEIGHT = 64                   # sprites are drawn small; keep the files small too


def sprite_name(icon_id):
    if icon_id in NO_SPRITE:
        return None
    return SPRITE_EXCEPTIONS.get(icon_id, f"MENU_MAP_{icon_id:02d}")


def load_atlases(dvd, helper):
    """-> {spriteName: (sheetName, x, y, w, h)}"""
    b = bnd4.BND4(dcx.decompress(dvd.read(LAYOUT_PATH), oodle=helper))
    atlas = {}
    sheets_seen = Counter()
    for e in b.entries:
        base = e.name.replace(chr(92), "/").split("/")[-1]
        if not base.lower().endswith(".layout"):
            continue
        sheet = base[:-len(".layout")]
        if sheet not in SHEETS:
            continue
        root = ET.fromstring(b.read(e).decode("utf-8", "replace"))
        for st in root.iter("SubTexture"):
            nm = (st.get("name") or "").rsplit(".", 1)[0]
            try:
                rect = (int(st.get("x")), int(st.get("y")),
                        int(st.get("width")), int(st.get("height")))
            except (TypeError, ValueError):
                continue
            atlas[nm] = (sheet, *rect)
            sheets_seen[sheet] += 1
    return atlas, sheets_seen


def used_icon_ids(game):
    """Every iconId referenced by the params we build markers from."""
    params = param.load_params(os.path.join(game, "regulation.bin"))
    ids = Counter()
    for pname, dname, field in (("WorldMapPointParam", "WorldMapPointParam", "iconId"),
                                ("BonfireWarpParam", "BonfireWarpParam", "iconId")):
        d = paramdef.load(os.path.join(DEFS, dname + ".xml"))
        for r in params[pname].rows:
            try:
                ids[d.get(r.data, field)] += 1
            except Exception:
                pass
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game-dir", default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "web", "icons"))
    args = ap.parse_args()

    game = require_game_dir(args.game_dir)
    t0 = time.time()
    dvd = DvdBnd(game, cache_dir=os.path.join(ROOT, "cache"), verbose=False)
    helper = oodle.make_helper(game)

    print("reading sprite atlases ...")
    atlas, sheets_seen = load_atlases(dvd, helper)
    print(f"  {len(atlas)} sprites across "
          + ", ".join(f"{k}={v}" for k, v in sorted(sheets_seen.items())))

    print("which icons do the params actually use ...")
    ids = used_icon_ids(game)
    print(f"  {len(ids)} distinct iconIds, {sum(ids.values())} references")

    wanted = {}
    missing = []
    for icon_id in sorted(ids):
        nm = sprite_name(icon_id)
        if nm is None:
            continue
        if nm not in atlas:
            missing.append(icon_id)
            continue
        wanted[icon_id] = nm
    print(f"  {len(wanted)} have a sprite; no sprite for {missing}")

    print(f"decoding the {len(SHEETS)} map-cursor sheets ...")
    tpf_bytes = dcx.decompress(dvd.read(TPF_PATH), oodle=helper)
    textures = {t.name: t for t in tpflib.parse(tpf_bytes)}
    sheets = {}
    for name in SHEETS:
        t = textures.get(name)
        if not t:
            print(f"  ! {name} not in the TPF")
            continue
        img, w, h = tpflib.texture_image(tpf_bytes, t)
        sheets[name] = img
        print(f"  {name}: {w}x{h}")

    os.makedirs(args.out, exist_ok=True)
    index = {}
    saved = 0
    for icon_id, nm in sorted(wanted.items()):
        sheet, x, y, w, h = atlas[nm]
        src = sheets.get(sheet)
        if src is None or w <= 0 or h <= 0:
            continue
        crop = src.crop((x, y, x + w, y + h))
        if h > MAX_HEIGHT:
            scale = MAX_HEIGHT / h
            crop = crop.resize((max(1, round(w * scale)), MAX_HEIGHT), Image.LANCZOS)
        path = os.path.join(args.out, f"{icon_id}.png")
        crop.save(path, "PNG", optimize=True)
        index[str(icon_id)] = {"file": f"icons/{icon_id}.png",
                               "w": crop.width, "h": crop.height,
                               "sprite": nm, "uses": ids[icon_id]}
        saved += 1

    # The index lives beside the sprites so the existing static handler serves
    # it; nothing about the server needs to change.
    doc = {"icons": index, "missing": sorted(missing)}
    out_json = os.path.join(args.out, "index.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    total = sum(os.path.getsize(os.path.join(args.out, f"{i}.png")) for i in wanted
                if os.path.exists(os.path.join(args.out, f"{i}.png")))
    print(f"\n{saved} icons -> {args.out}  ({total / 1024:.0f} KB)")
    print(f"index -> {out_json}")
    print(f"{time.time() - t0:.0f}s")

    print("\nmost-used icons:")
    for icon_id, meta in sorted(index.items(), key=lambda kv: -kv[1]["uses"])[:10]:
        print(f"   icon {icon_id:>4}  {meta['sprite']:<24}"
              f"{meta['w']:>4}x{meta['h']:<4}  used {meta['uses']}x")
    dvd.close()


if __name__ == "__main__":
    main()
