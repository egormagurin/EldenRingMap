"""Open the game archives and check which map-tile files are present.

Also answers the DLC question: if MENU_MapTile M10/M11 ids resolve, Shadow of
the Erdtree map data is installed.
"""
import sys
import os
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib.dvdbnd import DvdBnd, path_hash
from erlib.gamepath import require_game_dir

GAME = require_game_dir()
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cache")

PROBE_PATHS = [
    "/menu/71_maptile.tpfbhd",
    "/menu/71_maptile.tpfbdt",
    "/menu/71_maptile.mtmskbnd.dcx",
    "/regulation.bin",
    "/menu/menu.msgbnd.dcx",
    "/msg/engus/menu.msgbnd.dcx",
    "/msg/engus/item.msgbnd.dcx",
    "/map/mapstudio/m60_00_00_00.msb.dcx",
]


def main():
    t = time.time()
    print(f"opening archives in {GAME} ...")
    d = DvdBnd(GAME, cache_dir=CACHE)
    print(f"total files indexed: {len(d.by_hash):,}   ({time.time() - t:.1f}s)\n")

    print("--- probe known paths ---")
    for p in PROBE_PATHS:
        e = d.entry(p)
        if e:
            print(f"  FOUND    {p:<45} {e.size:>12,} B  in {e.archive}"
                  f"{'  [aes]' if e.aes_key else ''}")
        else:
            print(f"  missing  {p}")

    print("\n--- write out 71_maptile header + a sample ---")
    for p in ["/menu/71_maptile.tpfbhd", "/menu/71_maptile.mtmskbnd.dcx"]:
        if d.has(p):
            data = d.read(p)
            out = os.path.join(CACHE, os.path.basename(p))
            with open(out, "wb") as f:
                f.write(data)
            print(f"  {os.path.basename(p)}: {len(data):,} B  magic={data[:4]!r} -> {out}")

    d.close()


if __name__ == "__main__":
    main()
