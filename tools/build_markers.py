"""Build the map marker dataset from your installed regulation.bin + message files.

Every marker carries the event flag that the save file uses to record it, so the
live server can mark it found without any hand-authored data.

    python tools/build_markers.py            -> data/markers.json

Coordinate model (verified against the extracted 10496x10496 tile masters):

    S        = 256                      world units per overworld grid cell
    worldX   = gridX*S + S/2 + posX     each cell's centre is its local origin
    worldZ   = gridZ*S + S/2 + posZ
    px       = worldX - 7168
    py       = 16640 - worldZ

Legacy dungeons (m10_*, m11_*, m12_*, m3x_*) have their own local frame and are
translated onto the overworld through WorldMapLegacyConvParam, which is a pure
translation anchored at per-block base points.
"""
import json
import os
import sys
import math
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib import param, paramdef, fmg, oodle
from erlib.dvdbnd import DvdBnd
from erlib.gamepath import require_game_dir

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFS = os.path.join(ROOT, "data", "paramdefs")
GAME = require_game_dir(sys.argv[1] if len(sys.argv) > 1 else None)
REG = os.path.join(GAME, "regulation.bin")

TILE_WORLD = 256
OFFSET_X = -7168
OFFSET_Y = 16640

# Locale code -> the game's own message folder. Using the game's text means
# marker names read exactly as they do in-game, rather than being translated.
LOCALES = {"en": "engus", "ru": "rusru"}

# Only used for the handful of names we synthesise ourselves (see build()).
DERIVED = {
    "map_of":       {"en": "Map: {}",              "ru": "Карта: {}"},
    "map_fragment": {"en": "Map fragment {}",      "ru": "Фрагмент карты {}"},
    "boss_arena":   {"en": "Boss arena ({})",      "ru": "Арена босса ({})"},
    "landmark":     {"en": "Landmark",             "ru": "Точка на карте"},
    "landmark_near":{"en": "Landmark near {}",     "ru": "Точка рядом: {}"},
}

# Legacy blocks whose art lives on the underground master rather than the surface.
UNDERGROUND_BLOCKS = {(12, 1), (12, 2), (12, 3), (12, 4), (12, 5), (12, 7)}


def project(area, grid_x, grid_z, pos_x, pos_z):
    """Overworld grid + local offset -> master pixel."""
    world_x = grid_x * TILE_WORLD + TILE_WORLD / 2 + pos_x
    world_z = grid_z * TILE_WORLD + TILE_WORLD / 2 + pos_z
    return world_x + OFFSET_X, OFFSET_Y - world_z


def master_for_area(area):
    return "M10" if area == 61 else "M00"


# --------------------------------------------------------------- legacy dungeons

class LegacyConv:
    """WorldMapLegacyConvParam -> translate dungeon-local coords onto the overworld.

    Each row is a pure translation anchored at a base point. Two wrinkles that
    matter:

    * Not every row targets the overworld. Some hop to another dungeon
      (m13_00_00 -> m34_15_00 -> m60_51_46), so resolution has to follow chains.
    * A block that straddles several overworld cells gets one row per cell. They
      describe the same world point in different cell-local frames, so any of
      them yields identical world coordinates - the choice is arbitrary.
    """

    def __init__(self, rows, pdef):
        self.by_block = defaultdict(list)
        for r in rows:
            v = pdef.as_dict(r.data)
            self.by_block[(v["srcAreaNo"], v["srcGridXNo"], v["srcGridZNo"])].append(v)

    def _rows_for(self, area, block, mapno):
        return self.by_block.get((area, block, mapno)) or self.by_block.get((area, block, 0))

    def convert(self, area, block, mapno, x, y, z, _depth=0):
        """-> (px, py, dstArea) or None when the game does not place this block."""
        if area in (60, 61):
            px, py = project(area, block, mapno, x, z)
            return px, py, area
        if _depth > 4:
            return None
        rows = self._rows_for(area, block, mapno)
        if not rows:
            return None
        # prefer a row that lands straight on the overworld
        direct = [v for v in rows if v["dstAreaNo"] in (60, 61)]
        pool = direct or rows
        best = min(pool, key=lambda v: (v["srcPosX"] - x) ** 2 + (v["srcPosZ"] - z) ** 2)
        # translate into the destination map's local frame, then keep resolving
        nx = x - best["srcPosX"] + best["dstPosX"]
        ny = y - best["srcPosY"] + best["dstPosY"]
        nz = z - best["srcPosZ"] + best["dstPosZ"]
        return self.convert(best["dstAreaNo"], best["dstGridXNo"], best["dstGridZNo"],
                            nx, ny, nz, _depth + 1)


def place(area, block, mapno, x, y, z, conv):
    """Any (map, local position) -> (px, py, master) or None."""
    r = conv.convert(area, block, mapno, x, y, z)
    if r is None:
        return None
    px, py, dst_area = r
    if dst_area == 61:
        master = "M10"
    elif (area, block) in UNDERGROUND_BLOCKS:
        master = "M01"
    else:
        master = "M00"
    return px, py, master


def nearest_marker(markers, master, px, py, radius):
    """Closest already-built marker on the same master, if close enough."""
    best, best_d = None, radius * radius
    for m in markers:
        if m.get("master") != master or m.get("px") is None:
            continue
        d = (m["px"] - px) ** 2 + (m["py"] - py) ** 2
        if d < best_d:
            best_d, best = d, m
    return best


def derived_names(key, arg):
    """Localised name for the few markers whose text we synthesise."""
    return {loc: DERIVED[key][loc].format(arg) for loc in LOCALES}


# ---------------------------------------------------------------------- builders

def build(params, defs, names_by_loc, conv):
    """`names_by_loc` is {locale: {fmgName: {id: text}}}."""
    markers = []
    place_tables = {loc: names_by_loc[loc].get("PlaceName", {}) for loc in names_by_loc}

    def place_names(text_id):
        """-> {locale: name} or None when the id has no usable text.

        English is the reference: if an id has no English text we skip the
        marker entirely, and any locale missing that id falls back to English
        rather than showing an empty label.
        """
        en = place_tables["en"].get(text_id, "")
        if not en or en.startswith("%null%"):
            return None
        out = {}
        for loc in LOCALES:
            v = place_tables.get(loc, {}).get(text_id, "")
            out[loc] = en if (not v or v.startswith("%null%")) else v
        return out

    # ---- Sites of Grace -----------------------------------------------------
    d = defs["BonfireWarpParam"]
    for r in params["BonfireWarpParam"].rows:
        if r.id <= 0:
            continue
        v = d.as_dict(r.data, ["eventflagId", "bonfireEntityId", "areaNo", "gridXNo",
                               "gridZNo", "posX", "posY", "posZ", "textId1", "iconId",
                               "bonfireSubCategoryId"])
        if not v["eventflagId"]:
            continue
        p = place(v["areaNo"], v["gridXNo"], v["gridZNo"],
                  v["posX"], v["posY"], v["posZ"], conv)
        if p is None:
            continue
        nm = place_names(v["textId1"])
        if nm is None:
            continue
        markers.append({
            "id": f"grace:{r.id}",
            "cat": "grace",
            "names": nm,
            "flag": v["eventflagId"],
            "master": p[2], "px": round(p[0], 1), "py": round(p[1], 1),
            "map": f"m{v['areaNo']:02d}_{v['gridXNo']:02d}_{v['gridZNo']:02d}",
            "entity": v["bonfireEntityId"],
        })

    # ---- Bosses -------------------------------------------------------------
    d = defs["GameAreaParam"]
    for r in params["GameAreaParam"].rows:
        v = d.as_dict(r.data, ["defeatBossFlagId", "bossChallengeFlagId", "foundBossTextId",
                               "bossPosX", "bossPosY", "bossPosZ",
                               "bossMapAreaNo", "bossMapBlockNo", "bossMapMapNo"])
        flag = v["defeatBossFlagId"] or v["bossChallengeFlagId"]
        if not flag or not v["bossMapAreaNo"]:
            continue
        if v["bossPosX"] == 0 and v["bossPosZ"] == 0:
            continue
        p = place(v["bossMapAreaNo"], v["bossMapBlockNo"], v["bossMapMapNo"],
                  v["bossPosX"], v["bossPosY"], v["bossPosZ"], conv)
        if p is None:
            continue
        # GameAreaParam has no usable name field (foundBossTextId is a generic
        # "boss found" message), so borrow the nearest named landmark - in this
        # game the grace beside an arena is usually named after its boss.
        near = nearest_marker(markers, p[2], p[0], p[1], 170)
        nm = dict(near["names"]) if near else derived_names(
            "boss_arena", f"{v['bossMapAreaNo']:02d}_{v['bossMapBlockNo']:02d}")
        markers.append({
            "id": f"boss:{r.id}",
            "cat": "boss",
            "names": nm,
            "flag": v["defeatBossFlagId"] or None,
            "master": p[2], "px": round(p[0], 1), "py": round(p[1], 1),
            "map": f"m{v['bossMapAreaNo']:02d}_{v['bossMapBlockNo']:02d}_{v['bossMapMapNo']:02d}",
        })

    # ---- World map points (dungeon entrances, landmarks, POIs) --------------
    d = defs["WorldMapPointParam"]
    for r in params["WorldMapPointParam"].rows:
        v = d.as_dict(r.data, ["eventFlagId", "iconId", "areaNo", "gridXNo", "gridZNo",
                               "posX", "posY", "posZ", "textId1", "isAreaIcon"])
        p = place(v["areaNo"], v["gridXNo"], v["gridZNo"],
                  v["posX"], v["posY"], v["posZ"], conv)
        if p is None:
            continue
        nm = place_names(v["textId1"])
        if nm is None:
            # The game shows these as a bare icon with no label - they have no
            # text id at all. They are still real, individually flagged places,
            # so keep them rather than dropping 182 rows on the floor. Naming
            # them after the nearest named place is honest ("near X", not "is
            # X") and makes the popup useful.
            near = nearest_marker(markers, p[2], p[0], p[1], 400)
            if near:
                nm = {loc: DERIVED["landmark_near"][loc].format(near["names"][loc])
                      for loc in LOCALES}
            else:
                nm = {loc: DERIVED["landmark"][loc] for loc in LOCALES}
            markers.append({
                "id": f"landmark:{r.id}",
                "cat": "landmark",
                "names": nm,
                "flag": v["eventFlagId"] or None,
                "master": p[2], "px": round(p[0], 1), "py": round(p[1], 1),
                "map": f"m{v['areaNo']:02d}_{v['gridXNo']:02d}_{v['gridZNo']:02d}",
                "icon": v["iconId"],
            })
            continue
        markers.append({
            "id": f"poi:{r.id}",
            "cat": "region" if v["isAreaIcon"] else "poi",
            "names": nm,
            "flag": v["eventFlagId"] or None,
            "master": p[2], "px": round(p[0], 1), "py": round(p[1], 1),
            "map": f"m{v['areaNo']:02d}_{v['gridXNo']:02d}_{v['gridZNo']:02d}",
            "icon": v["iconId"],
        })

    # ---- Map fragments ------------------------------------------------------
    # openTravelArea{Left,Right,Top,Bottom} are already MASTER PIXELS, so a
    # fragment both places a marker and describes the region it reveals.
    # Row id ranges pick the master: <100 surface, <1000 underground, else DLC.
    d = defs["WorldMapPieceParam"]
    for r in params["WorldMapPieceParam"].rows:
        v = d.as_dict(r.data, ["openEventFlagId", "acquisitionEventFlagId",
                               "openTravelAreaLeft", "openTravelAreaRight",
                               "openTravelAreaTop", "openTravelAreaBottom"])
        # openEventFlagId is the persistent "this fragment is in your inventory"
        # flag; acquisitionEventFlagId is transient (it drives the pickup
        # animation) and reads false even for fragments you already hold.
        flag = v["openEventFlagId"] or v["acquisitionEventFlagId"]
        if not flag:
            continue
        left, right = v["openTravelAreaLeft"], v["openTravelAreaRight"]
        top, bottom = v["openTravelAreaTop"], v["openTravelAreaBottom"]
        master = "M00" if r.id < 100 else ("M01" if r.id < 1000 else "M10")
        cx, cy = (left + right) / 2, (top + bottom) / 2
        near = nearest_marker(markers, master, cx, cy, 900)
        nm = ({loc: DERIVED["map_of"][loc].format(near["names"][loc]) for loc in LOCALES}
              if near else derived_names("map_fragment", r.id))
        markers.append({
            "id": f"fragment:{r.id}", "cat": "fragment",
            "names": nm,
            "flag": flag, "master": master,
            "px": round(cx, 1), "py": round(cy, 1),
            "rect": [round(left, 1), round(top, 1), round(right, 1), round(bottom, 1)],
        })
    return markers


def dedupe(markers):
    """Ids >= 7 digits are globally unique; collapse those that landed twice."""
    seen = {}
    out = []
    for m in markers:
        key = (m["cat"], m["flag"], m["master"], m["px"], m["py"])
        if key in seen:
            continue
        seen[key] = True
        out.append(m)
    return out


def main():
    print(f"game dir: {GAME}")
    dvd = DvdBnd(GAME, cache_dir=os.path.join(ROOT, "cache"), verbose=False)
    helper = oodle.make_helper(GAME)

    print("loading params ...")
    params = param.load_params(REG)
    defs = {n: paramdef.load(os.path.join(DEFS, n + ".xml"))
            for n in ["BonfireWarpParam", "WorldMapPointParam", "WorldMapLegacyConvParam",
                      "WorldMapPieceParam", "GameAreaParam"]}
    for n, d in defs.items():
        actual = params[n].row_size
        flag = "ok" if d.row_size == actual else f"MISMATCH (def {d.row_size} vs param {actual})"
        print(f"  {n:<26} rows={params[n].row_count:<6} rowSize={actual:<5} {flag}")

    print("loading names ...")
    names_by_loc = {}
    for loc, folder in LOCALES.items():
        tables = {}
        for base_file in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx"]:
            path = f"/msg/{folder}/{base_file}"
            if not dvd.has(path):
                continue
            for fmg_name, table in fmg.load_msgbnd(dvd.read(path), oodle=helper).items():
                tables.setdefault(fmg_name.split("_dlc")[0], {}).update(table)
        names_by_loc[loc] = tables
        n = len(tables.get("PlaceName", {}))
        print(f"  {loc} ({folder}): PlaceName {n}" + ("" if n else "   <-- MISSING"))
    if not names_by_loc.get("en", {}).get("PlaceName"):
        sys.exit("no English names loaded - cannot continue")

    conv = LegacyConv(params["WorldMapLegacyConvParam"].rows, defs["WorldMapLegacyConvParam"])
    print(f"  legacy conv blocks: {len(conv.by_block)}")

    markers = dedupe(build(params, defs, names_by_loc, conv))
    dvd.close()

    by_cat = defaultdict(int)
    by_master = defaultdict(int)
    with_flag = 0
    for m in markers:
        by_cat[m["cat"]] += 1
        by_master[m["master"] or "-"] += 1
        if m.get("flag"):
            with_flag += 1

    print(f"\nmarkers: {len(markers)}  ({with_flag} carry an event flag)")
    print("  by category: " + ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())))
    print("  by master:   " + ", ".join(f"{k}={v}" for k, v in sorted(by_master.items())))

    placed = [m for m in markers if m["px"] is not None]
    if placed:
        xs = [m["px"] for m in placed]
        ys = [m["py"] for m in placed]
        oob = [m for m in placed if not (0 <= m["px"] <= 10496 and 0 <= m["py"] <= 10496)]
        print(f"  px range {min(xs):.0f}..{max(xs):.0f}   py range {min(ys):.0f}..{max(ys):.0f}")
        print(f"  out of bounds: {len(oob)}")

    conv_out = os.path.join(ROOT, "data", "legacy-conv.json")
    rows = []
    for (area, block, mapno), lst in conv.by_block.items():
        for v in lst:
            rows.append({
                "src": [area, block, mapno],
                "srcPos": [round(v["srcPosX"], 2), round(v["srcPosY"], 2), round(v["srcPosZ"], 2)],
                "dst": [v["dstAreaNo"], v["dstGridXNo"], v["dstGridZNo"]],
                "dstPos": [round(v["dstPosX"], 2), round(v["dstPosY"], 2), round(v["dstPosZ"], 2)],
            })
    with open(conv_out, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "undergroundBlocks": sorted(map(list, UNDERGROUND_BLOCKS))}, f)
    print(f"-> {conv_out}  ({len(rows)} rows)")

    out = os.path.join(ROOT, "data", "markers.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"locales": list(LOCALES), "markers": markers}, f, ensure_ascii=False)
    print(f"\n-> {out}  ({os.path.getsize(out):,} bytes)")

    print("\nsample graces:")
    for m in [x for x in markers if x["cat"] == "grace"][:8]:
        en = m["names"]["en"]
        ru = m["names"].get("ru", "")
        print(f"   {en[:32]:<34}{ru[:34]:<36}flag={m['flag']}")

    for loc in LOCALES:
        if loc == "en":
            continue
        same = sum(1 for m in markers if m["names"].get(loc) == m["names"]["en"])
        print(f"\n  {loc}: {len(markers) - same} localised, {same} fell back to English")


if __name__ == "__main__":
    main()
