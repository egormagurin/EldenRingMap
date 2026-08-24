"""Locate the Elden Ring install and the save file, without hardcoding paths.

Order of preference:
  1. an explicit argument or the ER_GAME_DIR / ER_SAVE env var
  2. every Steam library listed in libraryfolders.vdf, on every drive
  3. a few common install locations
"""
import glob
import os
import re


GAME_SUBPATH = os.path.join("steamapps", "common", "ELDEN RING", "Game")

_STEAM_ROOTS = [
    r"C:\Program Files (x86)\Steam",
    r"C:\Program Files\Steam",
]


def _drives():
    out = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.isdir(root):
            out.append(root)
    return out


def _steam_roots():
    """Steam installs, from the usual spots plus any <drive>:\\Steam*."""
    roots = [p for p in _STEAM_ROOTS if os.path.isdir(p)]
    for d in _drives():
        for name in ("Steam", "SteamLibrary", "Games\\Steam"):
            p = os.path.join(d, name)
            if os.path.isdir(p) and p not in roots:
                roots.append(p)
    return roots


def _library_folders():
    """Every Steam library path, read out of libraryfolders.vdf."""
    libs = []
    for root in _steam_roots():
        libs.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        if not os.path.isfile(vdf):
            continue
        try:
            text = open(vdf, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        # entries look like:   "path"    "D:\\Games\\Steam"
        for m in re.finditer(r'"path"\s*"([^"]+)"', text):
            p = m.group(1).replace("\\\\", "\\")
            if os.path.isdir(p) and p not in libs:
                libs.append(p)
    return libs


def find_game_dir(explicit=None):
    """The ...\\ELDEN RING\\Game folder, or None.

    Validated by the presence of regulation.bin, so a stale library entry or a
    half-uninstalled copy does not win.
    """
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("ER_GAME_DIR")
    if env:
        candidates.append(env)
    for lib in _library_folders():
        candidates.append(os.path.join(lib, GAME_SUBPATH))
    for d in _drives():
        candidates.append(os.path.join(d, "Games", "Steam", GAME_SUBPATH))

    for c in candidates:
        if not c:
            continue
        c = os.path.normpath(c)
        if os.path.isfile(os.path.join(c, "regulation.bin")):
            return c
        # tolerate being given the folder above Game/
        inner = os.path.join(c, "Game")
        if os.path.isfile(os.path.join(inner, "regulation.bin")):
            return inner
    return None


def find_save(explicit=None):
    """%APPDATA%\\EldenRing\\<steamId>\\ER0000.sl2 - most recently written."""
    if explicit and os.path.isfile(explicit):
        return explicit
    env = os.environ.get("ER_SAVE")
    if env and os.path.isfile(env):
        return env
    appdata = os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
    hits = glob.glob(os.path.join(appdata, "EldenRing", "*", "ER0000.sl2"))
    if not hits:
        return None
    return max(hits, key=os.path.getmtime)


def require_game_dir(explicit=None):
    d = find_game_dir(explicit)
    if not d:
        raise SystemExit(
            "Could not find your Elden Ring install.\n"
            "Pass it explicitly with --game-dir \"...\\ELDEN RING\\Game\", "
            "or set the ER_GAME_DIR environment variable.\n"
            "It is the folder containing eldenring.exe and regulation.bin."
        )
    return d
