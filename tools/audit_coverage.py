"""How much of the available marker data actually reaches the map?

For every source param, count the rows that became markers and bucket the ones
that didn't by reason. Anything large in a drop bucket is coverage we're losing.
"""
import sys
import os
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib import param, paramdef, fmg, oodle
from erlib.dvdbnd import DvdBnd
from erlib.gamepath import require_game_dir
from build_markers import LegacyConv, place

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFS = os.path.join(ROOT, "data", "paramdefs")
GAME = require_game_dir()


def main():
    dvd = DvdBnd(GAME, cache_dir=os.path.join(ROOT, "cache"), verbose=False)
    helper = oodle.make_helper(GAME)
    params = param.load_params(os.path.join(GAME, "regulation.bin"))
    defs = {n: paramdef.load(os.path.join(DEFS, n + ".xml"))
            for n in ["BonfireWarpParam", "WorldMapPointParam",
                      "WorldMapLegacyConvParam", "WorldMapPieceParam", "GameAreaParam"]}

    names = {}
    for f in ["item.msgbnd.dcx", "item_dlc02.msgbnd.dcx"]:
        p = f"/msg/engus/{f}"
        if dvd.has(p):
            for k, v in fmg.load_msgbnd(dvd.read(p), oodle=helper).items():
                names.setdefault(k.split("_dlc")[0], {}).update(v)
    place_names = names.get("PlaceName", {})
    conv = LegacyConv(params["WorldMapLegacyConvParam"].rows, defs["WorldMapLegacyConvParam"])

    def named(tid):
        n = place_names.get(tid, "")
        return bool(n) and not n.startswith("%null%")

    # ---------------- Sites of Grace ----------------
    d = defs["BonfireWarpParam"]
    drops = Counter()
    for r in params["BonfireWarpParam"].rows:
        if r.id <= 0:
            drops["row id <= 0"] += 1; continue
        v = d.as_dict(r.data, ["eventflagId", "areaNo", "gridXNo", "gridZNo",
                               "posX", "posY", "posZ", "textId1"])
        if not v["eventflagId"]:
            drops["no event flag"] += 1; continue
        if place(v["areaNo"], v["gridXNo"], v["gridZNo"], v["posX"], v["posY"], v["posZ"], conv) is None:
            drops[f"unplaceable (m{v['areaNo']:02d}_{v['gridXNo']:02d})"] += 1; continue
        if not named(v["textId1"]):
            drops["no English name"] += 1; continue
        drops["KEPT"] += 1
    report("BonfireWarpParam", params["BonfireWarpParam"].row_count, drops)

    # ---------------- World map points ----------------
    d = defs["WorldMapPointParam"]
    drops = Counter()
    for r in params["WorldMapPointParam"].rows:
        v = d.as_dict(r.data, ["eventFlagId", "areaNo", "gridXNo", "gridZNo",
                               "posX", "posY", "posZ", "textId1", "iconId"])
        if place(v["areaNo"], v["gridXNo"], v["gridZNo"], v["posX"], v["posY"], v["posZ"], conv) is None:
            drops[f"unplaceable (m{v['areaNo']:02d}_{v['gridXNo']:02d})"] += 1; continue
        if not named(v["textId1"]):
            drops["no English name"] += 1; continue
        drops["KEPT"] += 1
    report("WorldMapPointParam", params["WorldMapPointParam"].row_count, drops)

    # ---------------- Bosses ----------------
    d = defs["GameAreaParam"]
    drops = Counter()
    for r in params["GameAreaParam"].rows:
        v = d.as_dict(r.data, ["defeatBossFlagId", "bossChallengeFlagId", "bossPosX",
                               "bossPosY", "bossPosZ", "bossMapAreaNo",
                               "bossMapBlockNo", "bossMapMapNo"])
        if not (v["defeatBossFlagId"] or v["bossChallengeFlagId"]):
            drops["no boss flag"] += 1; continue
        if not v["bossMapAreaNo"]:
            drops["no map id"] += 1; continue
        if v["bossPosX"] == 0 and v["bossPosZ"] == 0:
            drops["position is 0,0"] += 1; continue
        if place(v["bossMapAreaNo"], v["bossMapBlockNo"], v["bossMapMapNo"],
                 v["bossPosX"], v["bossPosY"], v["bossPosZ"], conv) is None:
            drops[f"unplaceable (m{v['bossMapAreaNo']:02d}_{v['bossMapBlockNo']:02d})"] += 1; continue
        drops["KEPT"] += 1
    report("GameAreaParam", params["GameAreaParam"].row_count, drops)

    # ---------------- What else carries an event flag? ----------------
    print("\n" + "=" * 72)
    print("OTHER PARAMS THAT MIGHT YIELD MARKERS")
    print("=" * 72)
    interesting = ["ItemLotParam_map", "ItemLotParam_enemy", "ShopLineupParam",
                   "MapDefaultInfoParam", "PlayRegionParam", "AssetEnvironmentGeometryParam",
                   "NpcParam", "ObjActParam", "EnvObjLotParam", "RandomAppearParam"]
    for n in interesting:
        p = params.get(n)
        if not p:
            print(f"  {n:<32} (not in regulation.bin)")
            continue
        print(f"  {n:<32} {p.row_count:>7,} rows, rowSize {p.row_size}")

    dvd.close()


def report(name, total, drops):
    print("\n" + "=" * 72)
    kept = drops.pop("KEPT", 0)
    print(f"{name}: {total} rows -> {kept} markers ({kept / max(total,1) * 100:.0f}%)")
    print("=" * 72)
    for reason, n in drops.most_common(12):
        print(f"    {n:>5}  {reason}")


if __name__ == "__main__":
    main()
