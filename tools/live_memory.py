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
import argparse
import ctypes
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erlib.memory import Process, ProcessNotFound

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# `mov reg,[rip+rel32]` loading one of the game's global singletons.
# From soarqin/EROverlay src/hooking.cpp. Patterns rather than fixed offsets,
# because patterns usually survive a game patch and offsets never do.
SIGS = {
    "CSMenuManImp": "48 8B 0D ?? ?? ?? ?? 48 8B 49 08 E8 ?? ?? ?? ?? 48 8B D0 48 8B CE E8",
    "GameDataMan":  "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58 C3 C3",
    "EventFlagMan": "48 8B 3D ?? ?? ?? ?? 48 85 FF ?? ?? 32 C0 E9",
}

# CSMenuManImp -> +0x80 -> +LOC -> +0x24 == Location
#   struct Location { int32 mapId; float x; float y; int32 underground; float oriDeg; }
# 0x250 on 1.12+, 0x248 on 1.02-1.10.1. Both are tried and the plausible one wins.
LOCATION_OFFSETS = (0x250, 0x248)

# The map screen reports Roundtable Hold as a tiny box inside Limgrave, which
# would otherwise park the player dot in a field near Stormhill.
ROUNDTABLE_BOX = (2740.0, 7510.0, 2940.0, 7710.0)

MASTER_PX = 10496


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


class LiveReader:
    def __init__(self):
        self.proc = None
        self.menu = None
        self.loc_off = None
        self.addrs = {}

    def attach(self):
        """Open the game and resolve the pointers. False if not ready yet."""
        self.proc = Process("eldenring.exe")
        for name, sig in SIGS.items():
            hit = self.proc.scan(sig)
            self.addrs[name] = self.proc.resolve_rip(hit) if hit else None
        self.menu = self.addrs.get("CSMenuManImp")
        if not self.menu:
            raise RuntimeError(
                "CSMenuManImp signature not found - the game has probably been "
                "patched since these patterns were written")
        return True

    def _read_location(self, loc_off):
        addr = self.proc.chain(self.menu, [0x80, loc_off, 0x24])
        if not addr:
            return None
        raw = self.proc.read(addr, 20)
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

    @staticmethod
    def _pack(got):
        map_id, x, y, undr, ori = got
        underground = bool(undr & 1)
        if map_id == 10:
            master = "M11" if underground else "M10"
        else:
            master = "M01" if underground else "M00"
        x0, y0, x1, y1 = ROUNDTABLE_BOX
        in_roundtable = (map_id == 0 and x0 <= x < x1 and y0 <= y < y1)
        return {
            "type": "pos",
            "px": round(x, 1), "py": round(y, 1),
            "master": master,
            "angle": round(ori, 1),
            "mapId": map_id,
            "underground": underground,
            "roundtable": in_roundtable,
            "t": int(time.time() * 1000),
        }


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
            reader.proc = None
            now = time.time()
            if now - last_warn > 10:
                last_warn = now
                emit({"type": "status", "state": "waiting", "detail": str(e)})
            time.sleep(2.0)
        except Exception as e:
            attached = False
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
