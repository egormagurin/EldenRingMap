"""Extract ERR Rune Piece / Ember Piece collectible locations.

These are NOT treasure lots (ItemLotParam); ERR places them as MSB entities
(model AEG099_821 = Rune Piece, AEG099_822 = Ember Piece) whose positions live
in MapForGoblins' pre-extracted JSON (MIT-licensed). This projects them onto
the master map like every other marker.

    python tools/extract_pieces.py   -> data/pieces.json

Collected-state: ERR tracks pieces via GEOF geometry memory, not save flags,
so most pieces carry no event flag and stay visible until checked off by hand.
A handful (43) do have event flags, listed in _piece_final_map.json.
"""
import argparse
import json
import os
import sys

reconfigure = getattr(sys.stdout, "reconfigure", None)
if reconfigure:
    reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib import param, paramdef, fmg, oodle
import erlib.modfiles as modfiles
from erlib.dvdbnd import DvdBnd
from erlib.gamepath import require_game_dir
from build_markers import LegacyConv, place, LOCALES

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MFG = os.path.join(ROOT, "data", "mfg")

# goods id -> (category slug, icon, EN fallback name)
PIECES = {
    800010: ("rune_pieces", "rune_piece.png", "Rune Piece"),
    850010: ("ember_pieces", "ember_piece.png", "Ember Piece"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-dir", default=None)
    ap.add_argument("--mod-dir", default=None)
    args = ap.parse_args()

    game = require_game_dir(args.game_dir)
    mod = modfiles.find_mod_dir(args.mod_dir)
    dvd = DvdBnd(game, cache_dir=os.path.join(ROOT, "cache"), verbose=False)
    helper = oodle.make_helper(game)

    params = param.load_params(modfiles.regulation_path(game, mod))
    conv = LegacyConv(params["WorldMapLegacyConvParam"].rows,
                      paramdef.load(os.path.join(ROOT, "data", "paramdefs",
                                                 "WorldMapLegacyConvParam.xml")))

    # Names from the game's own GoodsName FMG.
    names_by_loc = {}
    for loc, folder in LOCALES.items():
        tables = {}
        for f in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx"]:
            p = f"/msg/{folder}/{f}"
            if modfiles.has(dvd, mod, p):
                data = modfiles.read(dvd, mod, p)
                for k, v in fmg.load_msgbnd(data, oodle=helper).items():
                    tables.setdefault(k.split("_dlc")[0], {}).update(v)
        names_by_loc[loc] = tables.get("GoodsName", {})

    en_goods = names_by_loc.get("en", {})

    def goods_name(loc, goods_id, fallback):
        v = names_by_loc.get(loc, {}).get(goods_id, "")
        if not v or v.startswith("%null%"):
            v = en_goods.get(goods_id, "")
        if not v or v.startswith("%null%"):
            v = fallback
        return v

    # event flags for the few pieces that have one (keyed by rounded coords+map)
    flags = {}
    flag_path = os.path.join(MFG, "_piece_final_map.json")
    if os.path.isfile(flag_path):
        for rec in json.load(open(flag_path, encoding="utf-8")):
            key = (rec["type"], rec["map"], round(rec["x"], 1), round(rec["z"], 1))
            flags[key] = rec.get("flag", 0)

    markers = []
    seen = set()
    for goods_id, (cat, icon, fallback) in PIECES.items():
        path = os.path.join(MFG, "rune_pieces.json" if goods_id == 800010
                            else "ember_pieces.json")
        if not os.path.isfile(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for piece in data:
            map_id = piece["map"]
            aa = int(map_id[1:3])
            bb = int(map_id[4:6])
            cc = int(map_id[7:9])
            tier = int(map_id[10:12]) if aa in (60, 61) else 0
            x, y, z = piece["x"], piece.get("y", 0.0), piece["z"]
            p = place(aa, bb, cc, x, y, z, conv, tier=tier)
            if p is None:
                continue
            px, py, master = p
            key = (round(px, 1), round(py, 1), master)
            if key in seen:
                continue
            seen.add(key)
            flag = flags.get(("rune" if goods_id == 800010 else "ember",
                              map_id, round(x, 1), round(z, 1)), 0) or None
            markers.append({
                "id": f"{cat}:{goods_id}:{len(markers)}",
                "cat": cat,
                "names": {loc: goods_name(loc, goods_id, fallback)
                          for loc in LOCALES},
                "flag": flag,
                "master": master, "px": round(px, 1), "py": round(py, 1),
                "map": map_id,
                "icon": icon,
            })

    out = os.path.join(ROOT, "data", "pieces.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"locales": list(LOCALES), "markers": markers}, f,
                  ensure_ascii=False)
    from collections import Counter
    counts = Counter(m["cat"] for m in markers)
    flagged = sum(1 for m in markers if m.get("flag"))
    print(f"pieces: {len(markers)} markers ({dict(counts)}), {flagged} with flags")
    print(f"-> {out}")
    dvd.close()


if __name__ == "__main__":
    main()
