"""Poll the running game for the player's live position.

Read-only. The process is opened with PROCESS_VM_READ only, so this cannot
modify the game; it also never touches your save file.

Emits one JSON object per line on stdout, which server/index.js consumes:

    {"type":"pos","px":3699.2,"py":7350.1,"master":"M00","angle":142.0,"t":...}
    {"type":"status","state":"waiting","detail":"..."}

Usage:
    python tools/live_memory.py                 # stream at 20 Hz
    python tools/live_memory.py --probe         # one-shot diagnostic + log

Requires administrator rights, because Elden Ring usually runs elevated (any
tool that touches it - FPS unlockers, autosplitters, save managers - needs the
same). Without them OpenProcess fails with error 5.
"""
# `X | None` annotations, without requiring Python 3.10.
from __future__ import annotations

import argparse
import ctypes
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)          # erlib lives beside this file, not under ROOT

# Same pointer chases either way; only the way memory is read differs. Windows
# goes through ReadProcessMemory, Linux through the Proton process's /proc.
if os.name == "nt":
    from erlib.memory import Process, ProcessNotFound
else:
    from erlib.memory_linux import Process, ProcessNotFound

# `mov reg,[rip+rel32]` loading one of the game's global singletons.
# From soarqin/EROverlay src/hooking.cpp. Patterns rather than fixed offsets,
# because patterns usually survive a game patch and offsets never do.
SIGS = {
    "CSMenuManImp": "48 8B 0D ?? ?? ?? ?? 48 8B 49 08 E8 ?? ?? ?? ?? 48 8B D0 48 8B CE E8",
    "GameDataMan":  "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58 C3 C3",
    "EventFlagMan": "48 8B 3D ?? ?? ?? ?? 48 85 FF ?? ?? 32 C0 E9",
    "WorldChrMan":  "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 0F 48 39 88",
}

# The map screen gives a master-map pixel, which has no vertical axis at all -
# the only way to a live height is the player's actual world position, which
# hangs off WorldChrMan.
#
# Each chain ends at the address of three floats (x, y, z) in the block's own
# local frame. The intermediate offsets move between game versions and none of
# them can be checked from the signature alone, so rather than betting on one,
# every chain is read and all the readings are sent. The server keeps whichever
# one is consistent with the map-screen pixel it already trusts (see
# liveHeight() in server/index.js) and ignores the rest, so a chain that is
# wrong or has moved yields no height rather than a confident wrong one.
PLAYER_CHAINS = (
    (0x1E508, 0x190, 0x68, 0x70),
    (0x1E508, 0x6B8, 0x68, 0x68, 0x70),
    (0x1E508, 0x190, 0x18, 0x70),
    (0x1E508, 0x58, 0x70),
)

# Anywhere outside this and the read is pointing at something that is not a
# position. The Lands Between is ~9km across; nothing legitimate is near 1e6.
WORLD_LIMIT = 100000.0

# Only --probe uses these, to show the same check the server applies.
TILE_WORLD = 256
OFFSET_X = -7168
OFFSET_Y = 16640

# CSMenuManImp -> +0x80 -> +LOC -> +0x24 == Location
#   struct Location { int32 mapId; float x; float y; int32 underground; float oriDeg; }
# 0x250 on 1.12+, 0x248 on 1.02-1.10.1. Both are tried and the plausible one wins.
LOCATION_OFFSETS = (0x250, 0x248)

# The map screen reports Roundtable Hold as a tiny box inside Limgrave, which
# would otherwise park the player dot in a field near Stormhill.
ROUNDTABLE_BOX = (2740.0, 7510.0, 2940.0, 7710.0)

MASTER_PX = 10496


def is_admin():
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


class LiveReader:
    def __init__(self):
        self.proc: Process | None = None
        self.menu: int | None = None
        self.loc_off: int | None = None
        self.addrs: dict[str, int | None] = {}

    def attach(self):
        """Open the game and resolve the pointers. False if not ready yet."""
        self.proc = Process("eldenring.exe")
        for name, sig in SIGS.items():
            hit = self.proc.scan(sig)
            self.addrs[name] = self.proc.resolve_rip(hit) if hit else None
        self.menu = self.addrs.get("CSMenuManImp")
        # Only the map screen is required. WorldChrMan is used for the live
        # height, which is an extra: without it the position still works.
        self.world = self.addrs.get("WorldChrMan")
        if not self.menu:
            raise RuntimeError(
                "CSMenuManImp signature not found - the game has probably been "
                "patched since these patterns were written")
        return True

    def _world_positions(self):
        """-> [{x,y,z}, ...], one per candidate chain that read plausibly.

        No attempt is made to pick between them here: this side has no way to
        tell a right answer from a wrong one. The server does that by checking
        each against the map-screen pixel.
        """
        proc = self.proc
        if proc is None or not self.world:
            return []
        out = []
        for chain in PLAYER_CHAINS:
            addr = proc.chain(self.world, list(chain))
            if not addr:
                continue
            raw = proc.read(addr, 12)
            if not raw:
                continue
            x, y, z = struct.unpack("<fff", raw)
            if not all(abs(v) < WORLD_LIMIT for v in (x, y, z)):
                continue
            if x == 0.0 and y == 0.0 and z == 0.0:
                continue
            out.append({"x": round(x, 3), "y": round(y, 3), "z": round(z, 3)})
        return out

    def _read_location(self, loc_off):
        proc = self.proc
        menu = self.menu
        if proc is None or menu is None:
            return None
        addr = proc.chain(menu, [0x80, loc_off, 0x24])
        if not addr:
            return None
        raw = proc.read(addr, 20)
        if not raw:
            return None
        map_id, x, y, undr, ori = struct.unpack("<iffif", raw)
        # Sanity: the map screen only ever reports 0 (Lands Between) or 10 (DLC),
        # and coordinates live inside the 10496px master.
        if map_id not in (0, 10):
            return None
        if not (0.0 <= x <= MASTER_PX and 0.0 <= y <= MASTER_PX):
            return None
        if x == 0.0 and y == 0.0:
            return None
        return map_id, x, y, undr, ori

    def location(self):
        """-> dict for one sample, or None while loading / in a menu."""
        if self.loc_off is not None:
            got = self._read_location(self.loc_off)
            if got:
                return self._pack(got)
            return None
        for off in LOCATION_OFFSETS:          # first successful read pins the offset
            got = self._read_location(off)
            if got:
                self.loc_off = off
                return self._pack(got)
        return None

    def _pack(self, got):
        map_id, x, y, undr, ori = got
        underground = bool(undr & 1)
        if map_id == 10:
            master = "M11" if underground else "M10"
        else:
            master = "M01" if underground else "M00"
        x0, y0, x1, y1 = ROUNDTABLE_BOX
        in_roundtable = (map_id == 0 and x0 <= x < x1 and y0 <= y < y1)
        frame = {
            "type": "pos",
            "px": round(x, 1), "py": round(y, 1),
            "master": master,
            "angle": round(ori, 1),
            "mapId": map_id,
            "underground": underground,
            "roundtable": in_roundtable,
            "t": int(time.time() * 1000),
        }
        worlds = self._world_positions()
        if worlds:
            frame["worlds"] = worlds
        return frame


def run_stream(hz):
    reader = LiveReader()
    interval = 1.0 / max(1, hz)
    attached = False
    last_warn = 0.0
    last_sent = None

    while True:
        try:
            if not attached:
                reader.attach()
                attached = True
                assert reader.proc is not None
                emit({"type": "status", "state": "attached",
                      "pid": reader.proc.pid,
                      "addrs": {k: (f"0x{v:X}" if v else None) for k, v in reader.addrs.items()}})
            loc = reader.location()
            if loc:
                # Only send when something actually moved - idle costs nothing.
                key = (loc["px"], loc["py"], loc["angle"], loc["master"])
                if key != last_sent:
                    last_sent = key
                    emit(loc)
            time.sleep(interval)

        except ProcessNotFound as e:
            attached = False
            if reader.proc:
                reader.proc.close()
            reader.proc = None
            now = time.time()
            if now - last_warn > 10:
                last_warn = now
                emit({"type": "status", "state": "waiting", "detail": str(e)})
            time.sleep(2.0)
        except Exception as e:
            attached = False
            if reader.proc:
                reader.proc.close()
            reader.proc = None
            emit({"type": "status", "state": "error", "detail": f"{type(e).__name__}: {e}"})
            time.sleep(3.0)


def run_probe():
    """One-shot diagnostic. Writes cache/live-probe.log as well as stdout."""
    lines = []

    def say(s):
        print(s)
        lines.append(s)

    say(f"admin: {is_admin()}")
    say(f"python: {sys.version.split()[0]} ({8 * struct.calcsize('P')}-bit)")
    try:
        reader = LiveReader()
        t0 = time.time()
        reader.attach()
        assert reader.proc is not None
        say(f"attached to pid {reader.proc.pid}, base 0x{reader.proc.base:X}, "
            f"image {reader.proc.size / 1e6:.1f} MB")
        for k, v in reader.addrs.items():
            say(f"  {k:<14} {'0x%X' % v if v else 'NOT FOUND'}")
        say(f"signature scan: {time.time() - t0:.1f}s")

        say("sampling location for 5s ...")
        seen = 0
        for _ in range(50):
            loc = reader.location()
            if loc:
                seen += 1
                if seen <= 10:
                    say(f"  {loc['master']}  px={loc['px']:8.1f} py={loc['py']:8.1f} "
                        f"angle={loc['angle']:6.1f}  mapId={loc['mapId']} "
                        f"underground={loc['underground']}"
                        + ("  [Roundtable Hold]" if loc["roundtable"] else ""))
                    # The height check the server does, shown here so a chain
                    # that has moved with a game patch is visible rather than
                    # just silently producing no height.
                    for i, w in enumerate(loc.get("worlds", [])):
                        block = (loc["px"] - OFFSET_X - TILE_WORLD / 2 - w["x"]) / TILE_WORLD
                        mapno = (OFFSET_Y - loc["py"] - TILE_WORLD / 2 - w["z"]) / TILE_WORLD
                        ok = all(abs(v - round(v)) < 0.01 and 0 <= round(v) <= 80
                                 for v in (block, mapno))
                        say(f"      chain {i}: x={w['x']:9.1f} y={w['y']:9.1f} "
                            f"z={w['z']:9.1f}  -> tile {block:7.2f},{mapno:7.2f} "
                            + ("MATCH - height %d" % round(w["y"]) if ok else "no match"))
            time.sleep(0.1)
        say(f"location offset used: "
            f"{'0x%X' % reader.loc_off if reader.loc_off else 'none found'}")
        say(f"got {seen}/50 samples")
        if seen == 0:
            say("  -> no readable location. Are you at the title screen or in a "
                "loading screen? Load a character and try again.")
    except ProcessNotFound as e:
        say(f"FAILED: {e}")
        if not is_admin():
            say("  -> run this as administrator (Elden Ring runs elevated)")
    except Exception as e:
        say(f"FAILED: {type(e).__name__}: {e}")

    os.makedirs(os.path.join(ROOT, "cache"), exist_ok=True)
    log = os.path.join(ROOT, "cache", "live-probe.log")
    with open(log, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nlog written to {log}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hz", type=int, default=20, help="samples per second (default 20)")
    ap.add_argument("--probe", action="store_true", help="one-shot diagnostic instead of streaming")
    args = ap.parse_args()

    if args.probe:
        run_probe()
        return
    if not is_admin():
        emit({"type": "status", "state": "error",
              "detail": "not running as administrator - Elden Ring runs elevated, "
                        "so its memory cannot be read"})
    run_stream(args.hz)


if __name__ == "__main__":
    main()
