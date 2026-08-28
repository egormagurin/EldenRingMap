import os
import re


_MAP_PREFIX = "/map/mapstudio/"
_MAP_NAME = re.compile(r"^(m\d{2}_\d{2}_\d{2}_\d{2})\.msb\.dcx$", re.IGNORECASE)


def find_mod_dir(explicit=None):
    candidate = explicit or os.environ.get("ER_MOD_DIR")
    if not candidate:
        return None
    candidate = os.path.normpath(candidate)
    return candidate if os.path.isdir(candidate) else None


def regulation_path(game_dir, mod_dir=None):
    if mod_dir:
        path = os.path.join(mod_dir, "regulation.bin")
        if os.path.isfile(path):
            return path
    return os.path.join(game_dir, "regulation.bin")


def loose_path(mod_dir, archive_path):
    if not mod_dir:
        return None
    normalized = archive_path.replace("\\", "/").lower()
    if normalized.startswith(_MAP_PREFIX):
        relative = os.path.join("map", "MapStudio", archive_path.rsplit("/", 1)[-1])
    else:
        relative = archive_path.lstrip("/").replace("/", os.sep)
    candidate = os.path.join(mod_dir, relative)
    return candidate if os.path.isfile(candidate) else None


def has(dvd, mod_dir, archive_path):
    return loose_path(mod_dir, archive_path) is not None or dvd.has(archive_path)


def read(dvd, mod_dir, archive_path):
    path = loose_path(mod_dir, archive_path)
    if path:
        with open(path, "rb") as source:
            return source.read()
    return dvd.read(archive_path)


def loose_map_ids(mod_dir):
    if not mod_dir:
        return {}
    root = os.path.join(mod_dir, "map", "MapStudio")
    try:
        names = os.listdir(root)
    except OSError:
        return {}
    found = {}
    for name in names:
        match = _MAP_NAME.match(name)
        if match:
            found[match.group(1).lower()] = os.path.getsize(os.path.join(root, name))
    return found
