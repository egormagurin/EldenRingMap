# How it works

Notes on the reverse engineering behind this project: how the save file is
decoded, how the map tiles come out of the game archives, and how world
coordinates become map pixels.

None of this is needed to use the map — see the [README](../README.md) for that.

---

## Reading the save

`ER0000.sl2` is a BND4 container of 12 entries: ten character slots plus a
profile summary and a regulation copy. Each entry is `[16-byte MD5][payload]`.

Elden Ring PC saves are **not encrypted** — the MD5 verifies directly against the
raw bytes. (An AES path exists in `server/lib/bnd4.js` as a fallback, but it is
never needed for a stock save.) That MD5 is doubly useful: it is a cheap change
detector, and because the file is *always* exactly 28,967,888 bytes, it is the
only reliable way to tell a finished write from one caught in progress.

A slot is a sequentially-serialised struct with five variable-length members, so
**nothing in it sits at a fixed offset**. We measured the event-flag bitfield move
by 2,216 bytes between two saves taken minutes apart. `server/lib/slotWalk.js`
walks every field in order, asserting the values the format guarantees — a
`FACE` magic, booleans that must be 0/1, a 0/8 enum, and a zero byte immediately
after the bitfield — so a mis-step fails loudly instead of returning plausible
garbage.

## Event flags

Progress lives in a 1,833,375-byte (`0x1BF99F`) bitfield. Flag lookup:

```
block  = flagId / 1000
index  = flagId % 1000
byte   = base + BLOCK_TABLE[block] * 125 + index / 8
bit    = 7 - (index % 8)                        // MSB-first
```

`BLOCK_TABLE` is `data/eventflag_bst.txt` (11,919 entries), from
[ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib). 125 bytes = exactly
1000 flags per block.

## Coordinates

The projection from world space to map pixels is exact — 1 pixel = 1 world unit,
no rotation:

```
S      = 256                            world units per overworld grid cell
worldX = gridX*S + S/2 + posX           each cell's centre is its local origin
worldZ = gridZ*S + S/2 + posZ
px     = worldX - 7168
py     = 16640 - worldZ
```

Legacy dungeons have their own local frames and are translated onto the overworld
via `WorldMapLegacyConvParam`. Some of its rows hop dungeon→dungeon
(`m13_00_00 → m34_15_00 → m60_51_46`), so resolution follows chains.

Sanity check: "The First Step" lands at px 3699, matching independently published
values to within a pixel.

## Map tiles

`menu/71_maptile.tpfbhd` indexes 28,469 tile textures. Each filename ends in a
variant bitmask — which map fragments the player holds, plus world-event bits.
To render a fully-revealed vanilla map you must pick, per cell, the variant
matching that cell's entry in `71_maptile.mtmskbnd`, indexed as
`lod*10000 + col*100 + row`.

Heuristics do **not** work here: "most bits set" disagrees with the real mask on
247 of 1369 cells, and the wrong pick swaps in art for a different world state,
producing a visible patchwork. With the mask table the match is 1369/1369.

Pipeline per tile: `Data0.bdt → 71_maptile.tpfbdt → DCX/Oodle → TPF → DDS(BC7)
→ RGBA → stitch → pyramid`. Oodle decompression calls the game's own
`oo2core_6_win64.dll`; BC7 decoding uses `texture2ddecoder`.

---

## Layout

```
server/
  index.js            HTTP + SSE + file watching (zero dependencies)
  lib/bnd4.js         BND4 container, MD5 verification, AES fallback
  lib/slotWalk.js     the forward struct walk + event-flag lookup
  lib/saveParser.js   save -> character list, torn-write tolerant
web/
  index.html, css/
  js/map.js     canvas tile engine
  js/app.js     markers, sidebar, live updates
  js/i18n.js    UI strings (EN/RU) + Russian pluralisation
tools/
  extract_tiles.py    game archives -> tile pyramid
  build_markers.py    regulation.bin -> markers.json
  er_save.py          standalone save inspector / reference implementation
  verify_markers.py   renders markers onto the master image to check the affine
  erlib/              dvdbnd, BHD5, DCX, Oodle, TPF, BND4, PARAM, PARAMDEF, FMG
server/lib/project.js   world position -> master pixel (also for legacy dungeons)
server/lib/liveMemory.js  spawns + supervises the optional live reader
tools/live_memory.py      read-only memory reader (position at 20 Hz)
tools/erlib/memory.py     ReadProcessMemory + AOB scanning via ctypes
data/
  eventflag_bst.txt   flag block -> group table
  markers.json        generated - markers with {names:{en,ru}}
  legacy-conv.json    generated - dungeon -> overworld translation
  paramdefs/          PARAMDEF XML from Paramdex
```
