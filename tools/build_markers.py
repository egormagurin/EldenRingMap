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
import struct
import sys
import math
from collections import defaultdict

reconfigure = getattr(sys.stdout, "reconfigure", None)
if reconfigure:
    reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib import param, paramdef, fmg, oodle, dcx
import erlib.modfiles as modfiles
from erlib.dvdbnd import DvdBnd
from erlib.gamepath import require_game_dir

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFS = os.path.join(ROOT, "data", "paramdefs")
GAME = require_game_dir(sys.argv[1] if len(sys.argv) > 1 else None)
MOD = modfiles.find_mod_dir()
REG = modfiles.regulation_path(GAME, MOD)

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
    "boss_near":    {"en": "Boss arena near {}",   "ru": "Арена босса рядом: {}"},
    "landmark":     {"en": "Landmark",             "ru": "Точка на карте"},
    "landmark_near":{"en": "Landmark near {}",     "ru": "Точка рядом: {}"},
}

# Legacy blocks whose art lives on the underground master rather than the surface.
UNDERGROUND_BLOCKS = {(12, 1), (12, 2), (12, 3), (12, 4), (12, 5), (12, 7)}


def project(area, grid_x, grid_z, pos_x, pos_z, tier=0):
    """Overworld grid + local offset -> master pixel.

    `tier` is the last digit of an overworld map id (m60_XX_YY_LL). The grid
    coarsens by a factor of two per tier, so a LOD-2 tile covers 1024 world
    units, not 256. The param tables only ever use tier 0, but map ids taken
    from MSB filenames do not - getting this wrong throws markers thousands of
    pixels off the map.
    """
    size = TILE_WORLD * (2 ** tier)
    world_x = grid_x * size + size / 2 + pos_x
    world_z = grid_z * size + size / 2 + pos_z
    return world_x + OFFSET_X, OFFSET_Y - world_z


def master_for_area(area):
    return "M10" if area == 61 else "M00"


# ------------------------------------------------------------------ boss names

# GameAreaParam has no name field - `foundBossTextId` is the generic "boss
# found" message - which is why every boss marker used to borrow the name of the
# nearest grace. The real name is not in the params at all: the game sets it
# when it draws the health bar, and that happens in an event script.
#
# Decompiling EMEVD is a project in itself, but we do not need to. The
# health-bar call passes the boss's entity id and its NpcName text id in the
# same argument blob, within a few words of each other, and both are exact
# values we already know - the entity id equals the defeat flag, and the text id
# has to be a live NpcName key. Scanning a small window around each defeat flag
# therefore either finds the right name or finds nothing; there is very little
# room to find a plausible wrong one, because a random word happening to be a
# live NpcName key is vanishingly unlikely (379 keys out of 2^32).
#
# Verified: m11_00_00_00 gives 11000800 -> "Morgott, the Omen King". Guessing
# from the enemy's model would have said "Margit" - both are c2130.
NAME_WINDOW = 16            # bytes either side of the flag, in 4-byte steps


def boss_names(dvd, helper, params, defs, name_table):
    """-> {defeatBossFlagId: [NpcName id, ...]} read out of the event scripts.

    Several ids is not ambiguity, it is a fight with more than one name:
    Godfrey/Hoarah Loux, Beast Clergyman/Maliketh, Radagon/Elden Beast, and the
    duo arenas. Sorting by id puts them in phase order in every case checked.
    """
    d = defs["GameAreaParam"]
    flags, files = {}, {"common", "common_func"}
    for r in params["GameAreaParam"].rows:
        v = d.as_dict(r.data, ["defeatBossFlagId", "bossMapAreaNo", "bossMapBlockNo",
                               "bossMapMapNo"])
        if not v["defeatBossFlagId"]:
            continue
        flags[struct.pack("<I", v["defeatBossFlagId"])] = v["defeatBossFlagId"]
        files.add("m%02d_%02d_%02d_00" % (v["bossMapAreaNo"], v["bossMapBlockNo"],
                                          v["bossMapMapNo"]))

    # Id 0 is the "DLC dummy" placeholder. A zero word appears in every event
    # blob, so leaving it in prefixes every boss on the map with it.
    live = {k for k, t in name_table.items()
            if k and t and not t.startswith("%null%")}
    found = defaultdict(set)
    read = 0
    for mid in sorted(files):
        path = f"/event/{mid}.emevd.dcx"
        if not modfiles.has(dvd, MOD, path):
            continue
        try:
            raw = dcx.decompress(modfiles.read(dvd, MOD, path), oodle=helper)
        except Exception:
            continue
        read += 1
        for packed, flag in flags.items():
            i = raw.find(packed)
            while i != -1:
                for delta in range(-NAME_WINDOW, NAME_WINDOW + 1, 4):
                    j = i + delta
                    if 0 <= j <= len(raw) - 4:
                        nid = struct.unpack_from("<I", raw, j)[0]
                        if nid in live:
                            found[flag].add(nid)
                i = raw.find(packed, i + 1)
    print(f"  event scripts: {read} read, {len(found)}/{len(flags)} bosses named")
    return {flag: sorted(ids) for flag, ids in found.items()}


# --------------------------------------------------------------- legacy dungeons

def anchor_rank(v):
    """Sort key that puts a block's real anchor row first (see LegacyConv)."""
    return (0 if v["dstAreaNo"] in (60, 61) else 1,     # lands on the overworld
            0 if v["isBasePoint"] else 1,               # the game's own base point
            0 if (v["srcPosX"] or v["srcPosZ"]) else 1, # names a source anchor...
            0 if (v["dstPosX"] or v["dstPosZ"]) else 1) # ...and a destination one


class LegacyConv:
    """WorldMapLegacyConvParam -> translate dungeon-local coords onto the overworld.

    Each row is a pure translation anchored at a base point. Two wrinkles that
    matter:

    * Not every row targets the overworld. Some hop to another dungeon
      (m13_00_00 -> m34_15_00 -> m60_51_46), so resolution has to follow chains.
    * A block that straddles several overworld cells gets one row per cell. They
      describe the same world point in different cell-local frames, so any of
      them yields identical world coordinates - the choice is arbitrary.

    ...except for three blocks where the rows disagree by hundreds of pixels,
    because the region's map art is drawn nowhere near where the region connects
    to the overworld: m13_00_00 (Farum Azula, 3673 px apart), m25_00_00 (the
    Finger Birthing Grounds, 912) and m15_00_00 (the Haligtree, 661). There the
    choice is not arbitrary, and choosing per point - nearest source anchor -
    scatters one region across two places. So the row is picked per block, and
    picked the way the game does: `isBasePoint` first, then the row that spells
    an anchor out rather than leaving it at the origin. Every other block's rows
    agree to within 36 px, so ordering them costs nothing.
    """

    def __init__(self, rows, pdef):
        self.by_block = defaultdict(list)
        for r in rows:
            v = pdef.as_dict(r.data)
            self.by_block[(v["srcAreaNo"], v["srcGridXNo"], v["srcGridZNo"])].append(v)
        for lst in self.by_block.values():
            lst.sort(key=anchor_rank)

    def _rows_for(self, area, block, mapno):
        return self.by_block.get((area, block, mapno)) or self.by_block.get((area, block, 0))

    def convert(self, area, block, mapno, x, y, z, _depth=0, tier=0):
        """-> (px, py, height, dstArea), or None if the game does not place this block.

        `height` is y after the same translation chain the horizontal axes go
        through, so it is a world height in the destination frame and heights
        from different blocks are comparable with each other.
        """
        if area in (60, 61):
            px, py = project(area, block, mapno, x, z, tier)
            return px, py, y, area
        if _depth > 4:
            return None
        rows = self._rows_for(area, block, mapno)
        if not rows:
            return None
        best = rows[0]                      # anchor_rank order, so one row per block
        # translate into the destination map's local frame, then keep resolving
        nx = x - best["srcPosX"] + best["dstPosX"]
        ny = y - best["srcPosY"] + best["dstPosY"]
        nz = z - best["srcPosZ"] + best["dstPosZ"]
        # a conv row always targets the tier-0 grid
        return self.convert(best["dstAreaNo"], best["dstGridXNo"], best["dstGridZNo"],
                            nx, ny, nz, _depth + 1, tier=0)


def place(area, block, mapno, x, y, z, conv, tier=0):
    """Any (map, local position) -> (px, py, master, height) or None."""
    r = conv.convert(area, block, mapno, x, y, z, tier=tier)
    if r is None:
        return None
    px, py, height, dst_area = r
    if dst_area == 61:
        master = "M10"
    elif (area, block) in UNDERGROUND_BLOCKS:
        master = "M01"
    else:
        master = "M00"
    return px, py, master, height


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

def build(params, defs, names_by_loc, conv, boss_name_ids):
    """`names_by_loc` is {locale: {fmgName: {id: text}}}."""
    markers = []
    place_tables = {loc: names_by_loc[loc].get("PlaceName", {}) for loc in names_by_loc}
    npc_tables = {loc: names_by_loc[loc].get("NpcName", {}) for loc in names_by_loc}

    def npc_names(ids):
        """-> {locale: 'Godfrey, First Elden Lord / Hoarah Loux, Warrior'} or None.

        Resolved per locale from the same ids, so Russian is the game's own text
        rather than a translation of the English. Identical strings collapse:
        Morgott's two phases share a name and should not be printed twice.
        """
        out = {}
        for loc in LOCALES:
            table = npc_tables.get(loc) or {}
            parts = []
            for i in ids:
                text = table.get(i) or npc_tables["en"].get(i, "")
                if text and not text.startswith("%null%") and text not in parts:
                    parts.append(text)
            if not parts:
                return None
            out[loc] = " / ".join(parts)
        return out

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
            "h": round(p[3]),
            "map": f"m{v['areaNo']:02d}_{v['gridXNo']:02d}_{v['gridZNo']:02d}",
            "entity": v["bonfireEntityId"],
            "icon": v["iconId"],
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
        # Prefer the boss's real name, read out of the event scripts. Where the
        # scripts do not yield one, fall back to the nearest named landmark -
        # but say "near X" rather than "X", because naming an arena after the
        # grace beside it is exactly what made these markers misleading.
        nm = npc_names(boss_name_ids.get(v["defeatBossFlagId"], []))
        if nm is None:
            # Graces only. Borrowing from another boss - which now carries a
            # real enemy name - produces "Boss arena near Malenia".
            graces = [x for x in markers if x["cat"] == "grace"]
            near = nearest_marker(graces, p[2], p[0], p[1], 170)
            nm = ({loc: DERIVED["boss_near"][loc].format(near["names"][loc])
                   for loc in LOCALES} if near else derived_names(
                "boss_arena", f"{v['bossMapAreaNo']:02d}_{v['bossMapBlockNo']:02d}"))
        markers.append({
            "id": f"boss:{r.id}",
            "cat": "boss",
            "names": nm,
            "flag": v["defeatBossFlagId"] or None,
            "master": p[2], "px": round(p[0], 1), "py": round(p[1], 1),
            "h": round(p[3]),
            "map": f"m{v['bossMapAreaNo']:02d}_{v['bossMapBlockNo']:02d}_{v['bossMapMapNo']:02d}",
        })

    # ---- World map points (dungeon entrances, landmarks, POIs) --------------
    d = defs["WorldMapPointParam"]
    for r in params["WorldMapPointParam"].rows:
        v = d.as_dict(r.data, ["eventFlagId", "iconId", "areaNo", "gridXNo", "gridZNo",
                               "posX", "posY", "posZ", "isAreaIcon", "angle"]
                              + [f"textId{i}" for i in range(1, 9)])
        p = place(v["areaNo"], v["gridXNo"], v["gridZNo"],
                  v["posX"], v["posY"], v["posZ"], conv)
        if p is None:
            continue
        # textId1 is usually the name, but a handful of rows only fill a later
        # slot - trying all eight recovers 8 real names for free.
        nm = None
        for slot in range(1, 9):
            nm = place_names(v.get(f"textId{slot}", -1))
            if nm is not None:
                break
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
            "h": round(p[3]),
                "map": f"m{v['areaNo']:02d}_{v['gridXNo']:02d}_{v['gridZNo']:02d}",
                "icon": v["iconId"],
                # non-zero only on the directional sprites (the grace rays and
                # summoning-pool flames), which must be rotated when drawn
                "angle": round(v.get("angle") or 0.0, 1) or None,
            })
            continue
        markers.append({
            "id": f"poi:{r.id}",
            "cat": "region" if v["isAreaIcon"] else "poi",
            "names": nm,
            "flag": v["eventFlagId"] or None,
            "master": p[2], "px": round(p[0], 1), "py": round(p[1], 1),
            "h": round(p[3]),
            "map": f"m{v['areaNo']:02d}_{v['gridXNo']:02d}_{v['gridZNo']:02d}",
            "icon": v["iconId"],
            "angle": round(v.get("angle") or 0.0, 1) or None,
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


# Categories where two rows on the same pixel with the same name really are one
# place. Leyndell, Royal Capital (m11_00_00) and Leyndell, Ashen Capital
# (m11_05_00) are two versions of the same map block, so five of its graces get
# a row - and an event flag - in each, at byte-identical coordinates. Drawn as
# two stacked pins the Ashen copy, which cannot be lit until the endgame, sits
# on top of the lit one and reads as an undiscovered grace.
#
# Bosses are deliberately NOT merged: Morgott and Godfrey share the Erdtree
# Sanctuary pixel the same way, but they are two different fights and killing
# one must not tick off the other. Item pickups are excluded for the same
# reason - several identical drops genuinely can sit on one spot.
MERGE_CATS = {"grace", "poi", "region", "landmark", "fragment"}
MERGE_RADIUS = 2.0          # px on the 10,496 px master


def merge_colocated(markers):
    """Collapse same-place, same-name duplicates into one marker with several flags."""
    out, taken = [], set()
    for i, a in enumerate(markers):
        if i in taken:
            continue
        taken.add(i)
        if a["cat"] not in MERGE_CATS or not a.get("flag"):
            out.append(a)
            continue
        flags = [a["flag"]]
        for j in range(i + 1, len(markers)):
            b = markers[j]
            if j in taken or b["cat"] != a["cat"] or b["master"] != a["master"]:
                continue
            if not b.get("flag") or b["names"]["en"] != a["names"]["en"]:
                continue
            if math.hypot(a["px"] - b["px"], a["py"] - b["py"]) > MERGE_RADIUS:
                continue
            taken.add(j)
            flags.append(b["flag"])
        if len(flags) > 1:
            # The server treats the marker as found when ANY of these is set.
            a = dict(a, flags=sorted(set(flags)))
        out.append(a)
    return out


def main():
    print(f"game dir: {GAME}")
    if MOD:
        print(f"mod dir:  {MOD}")
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
            if not modfiles.has(dvd, MOD, path):
                continue
            data = modfiles.read(dvd, MOD, path)
            for fmg_name, table in fmg.load_msgbnd(data, oodle=helper).items():
                tables.setdefault(fmg_name.split("_dlc")[0], {}).update(table)
        names_by_loc[loc] = tables
        n = len(tables.get("PlaceName", {}))
        print(f"  {loc} ({folder}): PlaceName {n}" + ("" if n else "   <-- MISSING"))
    if not names_by_loc.get("en", {}).get("PlaceName"):
        sys.exit("no English names loaded - cannot continue")

    conv = LegacyConv(params["WorldMapLegacyConvParam"].rows, defs["WorldMapLegacyConvParam"])
    print(f"  legacy conv blocks: {len(conv.by_block)}")

    print("reading boss names from the event scripts ...")
    named = boss_names(dvd, helper, params, defs, names_by_loc["en"].get("NpcName", {}))

    markers = dedupe(build(params, defs, names_by_loc, conv, named))
    stacked = len(markers)
    markers = merge_colocated(markers)
    stacked -= len(markers)
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
    if stacked:
        print(f"  merged {stacked} stacked duplicate marker(s) "
              f"(one place, two map-block versions)")
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
                "base": int(v["isBasePoint"]),
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
