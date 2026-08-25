"""Find which field of an MSB Treasure event holds the ItemLotParam id.

Rather than trusting a guessed offset, this reads every int in the event's
type-data block and checks it against the actual set of ItemLotParam_map row
ids. The offset that matches for (almost) every treasure event is the answer.
"""
import sys
import os
import struct
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib import msb as msblib, param, dcx, oodle
from erlib.dvdbnd import DvdBnd
from erlib.gamepath import require_game_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = require_game_dir()

SAMPLE_MAPS = ["m60_42_36_00", "m10_00_00_00", "m30_00_00_00", "m60_43_36_00"]


def main():
    dvd = DvdBnd(GAME, cache_dir=os.path.join(ROOT, "cache"), verbose=False)
    helper = oodle.make_helper(GAME)
    params = param.load_params(os.path.join(GAME, "regulation.bin"))
    lot_ids = set(params["ItemLotParam_map"].ids())
    enemy_ids = set(params["ItemLotParam_enemy"].ids())
    print(f"ItemLotParam_map ids: {len(lot_ids):,}  "
          f"range {min(lot_ids)}..{max(lot_ids)}")
    print(f"sample ids: {sorted(lot_ids)[:6]}\n")

    # offset -> how often the int there is a real map lot id
    hits = Counter()
    totals = Counter()
    type_counts = Counter()
    examples = defaultdict(list)

    for map_id in SAMPLE_MAPS:
        path = f"/map/mapstudio/{map_id}.msb.dcx"
        if not dvd.has(path):
            continue
        m = msblib.load(dcx.decompress(dvd.read(path), oodle=helper))
        for off, name in m.entries("EVENT_PARAM_ST"):
            etype = m.i32(off + 0x0C)
            type_counts[etype] += 1
            type_data = off + m.i64(off + 0x20)
            for o in range(0, 0x40, 4):
                try:
                    v = m.i32(type_data + o)
                except Exception:
                    break
                totals[o] += 1
                if v in lot_ids:
                    hits[o] += 1
                    if len(examples[o]) < 4:
                        examples[o].append((map_id, etype, v, name[:26]))

    print("event type distribution:", dict(type_counts.most_common()))
    print()
    print(f"{'typeData off':>13} {'matches':>9} {'of':>6}   examples")
    for o in sorted(totals):
        if hits[o]:
            ex = "; ".join(f"{e[2]}" for e in examples[o][:3])
            print(f"       +0x{o:02x} {hits[o]:>9} {totals[o]:>6}   {ex}")

    # which event type are the treasures?
    print("\nper-type match count at the best offset:")
    best = max(hits, key=lambda k: hits[k]) if hits else None
    if best is None:
        print("  no offset matched a map lot id at all")
        dvd.close()
        return
    print(f"  best offset = +0x{best:02x}")
    per_type = Counter()
    per_type_total = Counter()
    for map_id in SAMPLE_MAPS:
        path = f"/map/mapstudio/{map_id}.msb.dcx"
        if not dvd.has(path):
            continue
        m = msblib.load(dcx.decompress(dvd.read(path), oodle=helper))
        for off, name in m.entries("EVENT_PARAM_ST"):
            etype = m.i32(off + 0x0C)
            per_type_total[etype] += 1
            td = off + m.i64(off + 0x20)
            try:
                v = m.i32(td + best)
            except Exception:
                continue
            if v in lot_ids:
                per_type[etype] += 1
    for t in sorted(per_type_total):
        print(f"    type {t:>3}: {per_type[t]:>4} / {per_type_total[t]:>4} match")

    dvd.close()


if __name__ == "__main__":
    main()
