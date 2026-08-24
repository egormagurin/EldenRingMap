"""List the param files inside regulation.bin (diagnostic helper)."""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib import regulation, bnd4
from erlib.gamepath import require_game_dir

REG = os.path.join(require_game_dir(), "regulation.bin")


def short(name):
    return name.replace(chr(92), "/").split("/")[-1]


def main():
    b = bnd4.BND4(regulation.load(REG))
    print(f"regulation version {b.version}, {b.file_count} params")
    entries = sorted(b.entries, key=lambda e: short(e.name))

    keywords = sys.argv[1:] or ["Bonfire", "WorldMap", "MapArea", "ItemLot", "Map", "Grace", "Warp"]
    for kw in keywords:
        hits = [e for e in entries if kw.lower() in short(e.name).lower()]
        print(f"\n--- {kw} ({len(hits)}) ---")
        for e in hits[:30]:
            print(f"    {short(e.name):<45} {e.size:>9,} bytes  id={e.id}")

    print(f"\n--- all {len(entries)} params ---")
    for i in range(0, len(entries), 3):
        row = entries[i:i + 3]
        print("  " + "".join(f"{short(e.name):<42}" for e in row))


if __name__ == "__main__":
    main()
