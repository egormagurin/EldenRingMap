"""Read 71_maptile.mtmskbnd - the game's own table saying which tile variant
represents a fully-revealed cell.

Every map tile filename ends in an 8-hex-digit variant code. That code is a
bitmask of world state: which map fragments the player holds, plus world-event
bits (burned Erdtree, Ashen Capital, the crater). To render a fully-revealed
vanilla map you must pick, per cell, the variant whose code equals that cell's
authoritative mask.

Heuristics do not work here. "Most bits set" disagrees with the real mask on 247
of 1369 M00 cells, and the wrong pick is not subtly wrong - it swaps in art for a
different world state, producing a visible patchwork.

The table is XML: <MapTileMask exists="1" id="..." mask="..."/>, where

    id = lod * 10000 + col * 100 + row      (column-major - verified against
                                             1369/1369 M00 cells at LOD 0)

Cells with no row have no fragment-dependent art; use the plain 0x00000000
variant. M11 (DLC underground) has no mask rows at all and ships exactly one
variant per cell.
"""
import re
import xml.etree.ElementTree as ET

from . import dcx, bnd4

_FILE_RE = re.compile(r"MENU_MapTile_(M\d{2})\.mtmsk")


def load_masks(mtmskbnd_bytes, oodle=None):
    """-> {master: {id: mask}} for M00/M01/M10/M11."""
    b = bnd4.BND4(dcx.decompress(mtmskbnd_bytes, oodle=oodle))
    out = {}
    for e in b.entries:
        m = _FILE_RE.search(e.name)
        if not m:
            continue
        root = ET.fromstring(b.read(e).decode("utf-8", "replace"))
        out[m.group(1)] = {
            int(c.get("id")): int(c.get("mask"))
            for c in root
            if c.get("exists") == "1" and c.get("id") and c.get("mask")
        }
    return out


def mask_id(lod, col, row):
    return lod * 10000 + col * 100 + row


def choose_variant(codes, mask):
    """Pick the fully-revealed variant for one cell.

    `codes` are the hex strings present for the cell; `mask` is its table entry
    (or None). Falls back to the unmodified 0x00000000 tile, then to whatever
    exists, so a missing table row degrades to "plain art" rather than to noise.
    """
    as_int = {int(c, 16): c for c in codes}
    if mask is not None and mask in as_int:
        return as_int[mask]
    if 0 in as_int:
        return as_int[0]
    return as_int[min(as_int)]
