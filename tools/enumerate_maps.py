"""Discover every MSB map file in the archives.

The BHD5 index stores only a 64-bit hash of each path, never the path itself, so
files can't be listed - they can only be looked up. Map ids are highly regular
(mAA_BB_CC_DD), so we generate every plausible id, hash it, and keep the hits.
"""
import sys
import os
import time

reconfigure = getattr(sys.stdout, "reconfigure", None)
if reconfigure:
    reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import erlib.modfiles as modfiles
from erlib.dvdbnd import DvdBnd, path_hash
from erlib.gamepath import require_game_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def candidates():
    """Every mAA_BB_CC_DD we might plausibly see."""
    # All four components are two-digit. The overworld's Z index reaches the
    # high 50s, so none of these ranges can be tightened without losing tiles.
    for aa in range(0, 100):
        for bb in range(0, 100):
            for cc in range(0, 100):
                for dd in range(0, 4):
                    yield f"m{aa:02d}_{bb:02d}_{cc:02d}_{dd:02d}"


def main():
    game = require_game_dir()
    dvd = DvdBnd(game, cache_dir=os.path.join(ROOT, "cache"), verbose=False)
    have = dvd.by_hash
    print(f"archive index: {len(have):,} files\n")

    t0 = time.time()
    found = []
    tested = 0
    for name in candidates():
        tested += 1
        h = path_hash(f"/map/mapstudio/{name}.msb.dcx")
        e = have.get(h)
        if e:
            found.append((name, e.size, e.archive))
    by_name = {name: (size, archive) for name, size, archive in found}
    for name, size in modfiles.loose_map_ids(modfiles.find_mod_dir()).items():
        by_name[name] = (size, "mod")
    found = [(name, size, archive) for name, (size, archive) in by_name.items()]
    print(f"tested {tested:,} candidate map ids in {time.time() - t0:.1f}s")
    print(f"found {len(found)} MSB files\n")

    # group by area
    from collections import Counter, defaultdict
    by_area = Counter()
    overworld = defaultdict(list)
    total = 0
    for name, size, arch in found:
        aa = int(name[1:3])
        by_area[aa] += 1
        total += size
        if aa in (60, 61):
            bb, cc, dd = int(name[4:6]), int(name[7:9]), int(name[10:12])
            overworld[(aa, dd)].append((bb, cc))

    print(f"{'area':>6} {'files':>7}   what")
    LABELS = {
        10: "Stormveil / Chapel", 11: "Leyndell", 12: "Ainsel/Siofra/Deeproot/Mohgwyn",
        13: "Crumbling Farum Azula", 14: "Raya Lucaria", 15: "Haligtree",
        16: "Volcano Manor", 18: "Stranded Graveyard", 19: "Elden Throne",
        20: "Shadow Keep (DLC)", 21: "DLC legacy", 30: "Catacombs", 31: "Caves",
        32: "Tunnels", 34: "Divine Towers", 35: "Deathbed / misc", 39: "Gaols",
        40: "DLC dungeons", 41: "DLC dungeons", 42: "Roundtable / misc",
        43: "DLC misc", 45: "DLC gaols", 60: "OVERWORLD (Lands Between)",
        61: "OVERWORLD (Realm of Shadow)",
    }
    for aa in sorted(by_area):
        print(f"  m{aa:02d} {by_area[aa]:>7}   {LABELS.get(aa, '')}")
    print(f"\ntotal compressed size: {total / 1e6:.0f} MB")

    for (aa, lod) in sorted(overworld):
        cells = overworld[(aa, lod)]
        xs = [c[0] for c in cells]
        zs = [c[1] for c in cells]
        print(f"  m{aa}_*_*_{lod:02d}: {len(cells):>4} tiles   "
              f"X {min(xs)}-{max(xs)}   Z {min(zs)}-{max(zs)}")

    out = os.path.join(ROOT, "cache", "map-list.txt")
    with open(out, "w", encoding="utf-8") as f:
        for name, size, arch in sorted(found):
            f.write(f"{name}\t{size}\t{arch}\n")
    print(f"\n-> {out}")
    dvd.close()


if __name__ == "__main__":
    main()
