"""Extract item pickup locations from the game's MSB map files.

An item pickup is spread across three files:

  * the MSB places a PART (a chest, a corpse, a glowing item) with a position,
  * an MSB EVENT of type 4 (Treasure) links that part to an ItemLotParam id,
  * ItemLotParam_map says which items the lot gives and, crucially, which event
    flag the save sets once you have picked it up.

Joining those gives a marker that ticks itself off, exactly like a Site of Grace.

    python tools/extract_items.py            -> data/items.json

All offsets below were derived by reading a real MSB and cross-checking against
the param tables - see probe_msb_treasure.py for the method.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib import msb as msblib, param, paramdef, fmg, dcx, oodle
from erlib.dvdbnd import DvdBnd
from erlib.gamepath import require_game_dir
from build_markers import LegacyConv, place, LOCALES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFS = os.path.join(ROOT, "data", "paramdefs")

# --- MSB offsets, all verified empirically -----------------------------------
EVENT_TYPE_TREASURE = 4
EV_TYPE = 0x0C            # int32, event type
EV_TYPEDATA_PTR = 0x20    # int64, offset (entry-relative) of the type-data block
TD_PART_INDEX = 0x08      # int32, index into PARTS_PARAM_ST
TD_ITEM_LOT = 0x10        # int32, ItemLotParam_map row id
PART_POSITION = 0x20      # 3 x float32, local position

# lotItemCategory -> the FMG table holding that item's name. Resolved
# empirically at runtime and asserted against these expectations.
CATEGORY_TABLES = {
    1: "GoodsName",
    2: "WeaponName",
    3: "ProtectorName",
    4: "AccessoryName",
    6: "GemName",
}

# Items worth their own map layer. Everything else is lumped into "misc" so the
# map isn't drowned in Smithing Stones.
NOTABLE = {
    "seed":     ["golden seed"],
    "tear":     ["sacred tear", "crystal tear"],
    "talisman": [],                      # whole AccessoryName category
    "ash":      [],                      # whole GemName category
    "cookbook": ["cookbook"],
    "bearing":  ["bell bearing"],
    "whetblade": ["whetblade"],
    "spirit":   ["ashes"],               # spirit summons
}


def categorise(names, category):
    """-> marker category string for one lot's headline item."""
    low = (names or "").lower()
    if category == 4:
        return "talisman"
    if category == 6:
        return "ash"
    for cat, needles in NOTABLE.items():
        for n in needles:
            if n and n in low:
                return cat
    if category == 2:
        return "weapon"
    if category == 3:
        return "armor"
    return "misc"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game-dir", default=None)
    ap.add_argument("--limit", type=int, default=0, help="only N maps (for testing)")
    args = ap.parse_args()

    game = require_game_dir(args.game_dir)
    t0 = time.time()
    dvd = DvdBnd(game, cache_dir=os.path.join(ROOT, "cache"), verbose=False)
    helper = oodle.make_helper(game)

    print("loading params ...")
    params = param.load_params(os.path.join(game, "regulation.bin"))
    lot_def = paramdef.load(os.path.join(DEFS, "ItemLotParam.xml"))
    conv = LegacyConv(params["WorldMapLegacyConvParam"].rows,
                      paramdef.load(os.path.join(DEFS, "WorldMapLegacyConvParam.xml")))
    lots = {r.id: r for r in params["ItemLotParam_map"].rows}
    print(f"  ItemLotParam_map: {len(lots):,} rows")

    print("loading item names ...")
    names_by_loc = {}
    for loc, folder in LOCALES.items():
        tables = {}
        for f in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx"]:
            p = f"/msg/{folder}/{f}"
            if dvd.has(p):
                for k, v in fmg.load_msgbnd(dvd.read(p), oodle=helper).items():
                    tables.setdefault(k.split("_dlc")[0], {}).update(v)
        names_by_loc[loc] = tables
    en = names_by_loc["en"]
    print("  " + ", ".join(f"{t}={len(en.get(t, {}))}" for t in CATEGORY_TABLES.values()))

    def item_name(loc, item_id, category):
        tbl = CATEGORY_TABLES.get(category)
        if not tbl:
            return ""
        v = names_by_loc.get(loc, {}).get(tbl, {}).get(item_id, "")
        if not v or v.startswith("%null%"):
            v = en.get(tbl, {}).get(item_id, "")
        return "" if v.startswith("%null%") else v

    # ---- walk every map -----------------------------------------------------
    map_list = os.path.join(ROOT, "cache", "map-list.txt")
    if not os.path.exists(map_list):
        sys.exit("run tools/enumerate_maps.py first (creates cache/map-list.txt)")
    map_ids = [l.split("\t")[0] for l in open(map_list, encoding="utf-8") if l.strip()]
    if args.limit:
        map_ids = map_ids[:args.limit]
    print(f"\nscanning {len(map_ids)} MSB files ...")

    placements = {}          # lotId -> (mapId, x, y, z)
    stats = Counter()
    for i, map_id in enumerate(map_ids):
        path = f"/map/mapstudio/{map_id}.msb.dcx"
        if not dvd.has(path):
            continue
        try:
            m = msblib.load(dcx.decompress(dvd.read(path), oodle=helper))
        except Exception as exc:
            stats["msb parse failed"] += 1
            continue
        parts = m.lists.get("PARTS_PARAM_ST")
        part_offsets = parts.entry_offsets if parts else []
        for off, _name in m.entries("EVENT_PARAM_ST"):
            if m.i32(off + EV_TYPE) != EVENT_TYPE_TREASURE:
                continue
            stats["treasure events"] += 1
            td = off + m.i64(off + EV_TYPEDATA_PTR)
            lot_id = m.i32(td + TD_ITEM_LOT)
            if lot_id not in lots:
                stats["lot id not in param"] += 1
                continue
            idx = m.i32(td + TD_PART_INDEX)
            if not (0 <= idx < len(part_offsets)):
                stats["part index out of range"] += 1
                continue
            x, y, z = m.vec3(part_offsets[idx] + PART_POSITION)
            # keep the first placement we see; later LOD tiles repeat them
            placements.setdefault(lot_id, (map_id, x, y, z))
        if (i + 1) % 200 == 0:
            print(f"    {i + 1}/{len(map_ids)} maps  ({len(placements):,} lots so far)")

    print(f"\n  {stats['treasure events']:,} treasure events -> "
          f"{len(placements):,} distinct item lots")
    for k, v in stats.most_common():
        if k != "treasure events":
            print(f"    {v:,} {k}")

    # ---- join to items + flags ---------------------------------------------
    markers = []
    dropped = Counter()
    cat_counts = Counter()
    for lot_id, (map_id, x, y, z) in sorted(placements.items()):
        row = lots[lot_id]
        flag = lot_def.get(row.data, "getItemFlagId")
        if not flag:
            dropped["no pickup flag"] += 1
            continue
        aa, bb, cc = int(map_id[1:3]), int(map_id[4:6]), int(map_id[7:9])
        p = place(aa, bb, cc, x, y, z, conv)
        if p is None:
            dropped[f"unplaceable m{aa:02d}_{bb:02d}"] += 1
            continue

        # headline item = first non-empty slot
        picked = None
        for s in range(1, 9):
            iid = lot_def.get(row.data, f"lotItemId{s:02d}")
            cat = lot_def.get(row.data, f"lotItemCategory{s:02d}")
            if iid and cat:
                nm = item_name("en", iid, cat)
                if nm:
                    picked = (iid, cat, nm)
                    break
        if not picked:
            dropped["no resolvable item name"] += 1
            continue
        iid, cat, en_name = picked
        loc_names = {loc: (item_name(loc, iid, cat) or en_name) for loc in LOCALES}
        mcat = categorise(en_name, cat)
        cat_counts[mcat] += 1
        markers.append({
            "id": f"item:{lot_id}",
            "cat": mcat,
            "names": loc_names,
            "flag": flag,
            "master": p[2], "px": round(p[0], 1), "py": round(p[1], 1),
            "map": map_id,
            "lot": lot_id,
        })

    print(f"\nitem markers: {len(markers):,}")
    print("  by category: " + ", ".join(f"{k}={v}" for k, v in cat_counts.most_common()))
    if dropped:
        print("  dropped: " + ", ".join(f"{k}={v}" for k, v in dropped.most_common(6)))
    by_master = Counter(m["master"] for m in markers)
    print("  by master:   " + ", ".join(f"{k}={v}" for k, v in by_master.most_common()))

    out = os.path.join(ROOT, "data", "items.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"locales": list(LOCALES), "markers": markers}, f, ensure_ascii=False)
    print(f"\n-> {out}  ({os.path.getsize(out):,} bytes)   {time.time() - t0:.0f}s")

    print("\nsample:")
    for m in markers[:10]:
        print(f"   {m['names']['en'][:34]:<36}{m['names'].get('ru','')[:30]:<32}"
              f"{m['cat']:<10}flag={m['flag']}")
    dvd.close()


if __name__ == "__main__":
    main()
