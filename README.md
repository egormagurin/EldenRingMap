# Elden Ring — Live Map

An interactive map of The Lands Between and the Realm of Shadow that **updates
itself while you play**. Rest at a new Site of Grace and it lights up. Kill a
boss and it gets a checkmark. Turn on real-time mode and your character becomes
a dot that moves with you.

Everything runs on your own PC. Nothing is uploaded, and there is no account.

Everything you see is built from **your own copy of the game**: the map is the
real in-game map art, and the markers come from the game's own data files. No
map tiles or marker data ship with this repository — you generate them once
during setup, in about two minutes.

---

## What you get

- **Four map layers** — The Lands Between, the Underground (Siofra / Ainsel /
  Deeproot), the Realm of Shadow, and the DLC underground.
- **3,506 markers that track themselves** — 413 Sites of Grace, 208 boss arenas,
  294 points of interest, 157 unnamed landmarks, 34 map fragments, and **2,400
  item pickups**: Golden Seeds, Sacred Tears, talismans, cookbooks, bell
  bearings, whetblades, weapons and armour.
- **The game's own map icons** — graces, catacombs, caves, churches and the rest
  are drawn with the real sprites lifted out of the game, not coloured dots.
- **Live progress.** Found markers turn green, and a popup names whatever you
  just discovered. Progress bars per category.
- **How to get there.** Click any marker and it tells you the nearest Site of
  Grace, whether that grace is lit yet, and which way to ride from it — plus how
  far the place is from where you are.
- **Your character** — level, playtime, deaths, all eight stats, runes.
- **Real-time position** (optional) — a dot that moves as you move.
- **English and Russian**, using the game's own text for every marker name.
- Search, marker clustering, manual check-off, and a "hide found" filter.
- Categories toggle independently, so you can show just Golden Seeds, or just
  what you haven't picked up yet.

---

## Requirements

| | |
|---|---|
| Windows | 10 or 11 |
| Elden Ring | installed — the map art is read out of your install |
| [Node.js](https://nodejs.org) | 18 or newer (LTS is fine) |
| [Python](https://python.org) | 3.9 or newer — **tick "Add Python to PATH"** in the installer |

About 65 MB of disk for the generated map tiles and icons.

---

## Setup — once, about two minutes

**1. Get the files**

```bash
git clone https://github.com/egormagurin/EldenRingMap.git
cd EldenRingMap
```

**2. Run `Setup.bat`**

Double-click it. It finds your Elden Ring install, installs a few Python
packages, extracts the map tiles and icons, builds the marker list, and reads
all 864 of the game's map files to find where every item is. You only need to do
this again after a game update.

If it can't find your install, open `Setup.bat` in Notepad and set the path
by hand near the top:

```bat
set GAMEDIR=D:\Games\Steam\steamapps\common\ELDEN RING\Game
```

That must be the folder containing `eldenring.exe` and `regulation.bin`. In
Steam: right-click Elden Ring → Manage → Browse local files, then open the
`Game` subfolder and copy the address bar.

---

## Using it

**Double-click `Start Map.bat`.** Your browser opens at
`http://localhost:8099`. Leave the black console window open while you play —
closing it stops the map.

Your save is found automatically. Start the game, play, and the map keeps up on
its own.

| Control | |
|---|---|
| Drag | pan |
| Scroll / double-click | zoom |
| Click a marker | details, how to get there, and a manual check-off button |
| `/` | jump to search |
| `Esc` | close popups |
| ◎ button | centre on your character |

The **EN / RU** buttons at the top switch language. Marker names are the game's
own translations, so they read exactly as they do in-game.

### On your phone or tablet

Run `"Start Map.bat" --lan`. It prints a second address:

```
open  http://localhost:8099
LAN   http://192.168.1.42:8099
```

Open that one on any device on the same Wi-Fi. Windows will ask about the
firewall the first time — allow it for **private networks only**.

### Real-time position (optional)

`Start Map.bat` updates whenever the game saves, which Elden Ring does
constantly, so progress stays current within a few seconds. The one thing it
can't do is move your dot smoothly — it jumps once per save.

**`Start Map LIVE.bat`** fixes that by reading the running game, giving a dot
that moves at 20 fps with a facing arrow. It asks for administrator rights,
because Elden Ring itself runs elevated.

> **Read-only.** The reader opens the game with read-only access. It cannot
> modify the game, and it never touches your save.

> **Offline play only.** Anti-cheat objects to anything reading game memory. If
> you play online through `start_protected_game.exe`, use the normal
> `Start Map.bat`. Real-time mode is for offline or modded setups where EAC
> isn't running.

`Check Live Mode.bat` tests whether it can attach to your game.

---

## Problems and fixes

### The window opens and closes instantly

Almost always **another copy is still running** and holding the port. The
launcher checks for this and names the process, but if the window closes too
fast to read, open a terminal in the folder and run `npm start` to see the
message.

Fix: close the other console window, or end `node.exe` in Task Manager.

### "Node.js was not found" / "Python not found"

They aren't on your PATH. Reinstall and make sure **"Add to PATH"** is ticked —
Python's installer has this as a checkbox on the first page, easy to miss. Then
open a *new* console; PATH changes don't reach already-open windows.

### "Map tiles are missing. Run Setup.bat once first."

Setup hasn't been run, or it failed partway. Run `Setup.bat` and read its output.

### "Could not find your Elden Ring install"

Auto-detection scans your Steam libraries. If your copy lives somewhere unusual,
set `GAMEDIR` near the top of `Setup.bat`. It needs the `Game` subfolder — the
one with `eldenring.exe` in it, not the folder above.

### Setup fails while installing Python packages

Run it by hand to see the real error:

```bash
python -m pip install zstandard pycryptodome pillow texture2ddecoder numpy
```

If pip itself is missing: `python -m ensurepip --upgrade`.

### "Could not find ER0000.sl2"

The save normally lives at `%APPDATA%\EldenRing\<your steam id>\ER0000.sl2`. If
yours is elsewhere:

```bash
npm start -- --save "C:\path\to\ER0000.sl2"
```

### Everything is grey / nothing shows as found

Only the **first occupied save slot** is displayed. If your character is in a
later slot, that's a current limitation.

### Progress isn't updating

The map updates when the game writes a save. Rest at a grace, or open and close
a menu, to force one. The console window prints a line for every update:

```
[watch] save changed: Tarnished lv57 207/949
```

### Real-time mode says it needs administrator rights

Elden Ring runs elevated, so the reader must too. Use `Start Map LIVE.bat`,
which requests elevation itself, rather than starting the server by hand.

### Real-time mode stopped working after a game update

A patch can move the internal structures the reader looks for. Run
`Check Live Mode.bat` — if it reports `NOT FOUND` for `CSMenuManImp`, the byte
signatures in `tools/live_memory.py` need updating for the new version.

Everything else keeps working meanwhile; only the moving dot is affected.

### The map art looks patchy or wrong after a game update

Re-run `Setup.bat`. Patches occasionally change the map textures and the game
data the markers come from.

### A grace I've rested at shows as undiscovered

If it's in Leyndell, this was a bug — fixed in 1.2.1. Re-run `Setup.bat` (or
just `python tools/build_markers.py`) and restart the map.

Elsewhere, check the marker really is the one you think: two different places
can sit close together, and boss arenas borrow the name of the nearest grace.

### An item shows as found that I haven't picked up

Some lots are shared between several placements. If one is picked up, the flag
is set for all of them. This is uncommon.

### Boss names look wrong

They're best-effort. The game's data has boss positions and defeat flags but no
usable name field, so each boss borrows the name of the nearest landmark. That's
usually right — a grace beside an arena is normally named after its boss — but
not always.

---

## Known limitations

- Only the **first occupied save slot** is shown.
- **Not every item is placed.** 2,400 pickups come from the game's map files;
  some others are spawned by event scripts and aren't covered. Enemy drops are
  not included either.
- **Shadow of the Erdtree items are missing.** The base game ships the DLC's map
  art and text, so the DLC map layer and its graces/bosses do appear — but the
  DLC's own map files are only present if you own and have installed it.
- **Boss names are derived**, as above.
- A few interior areas the game itself never places on the world map (Roundtable
  Hold, some arenas) are skipped.

---

## Is this safe? Can I get banned?

The normal mode is completely passive. It opens your save file for reading,
never writes to it, never touches the game process, and never talks to the
internet. There is nothing for anti-cheat to see.

**Real-time mode** reads the running game's memory. That is read-only and cannot
modify anything, but anti-cheat systems object to memory reading on principle.
Use it offline only — the same advice that applies to any Elden Ring mod, FPS
unlocker, or speedrun timer.

---

## Sharing and forking

The code is free to copy and modify. The **map tiles and marker names are not** —
those are FromSoftware's artwork and text, which is why setup generates them
from your own installation instead of shipping them.

If you fork this, keep `web/tiles/`, `cache/` and the generated files in `data/`
out of your commits. The included `.gitignore` already handles that.

Hosting a working copy as a public website isn't possible in any case: a page on
a web server can't read a save file on your PC, which is the whole point of the
tool.

---

## Changelog

### 1.2.1 — fixes

*Five Leyndell graces never went green.* Leyndell exists twice in the game's
data — Royal Capital and Ashen Capital — and Elden Throne, Erdtree Sanctuary,
East Capital Rampart, Queen's Bedchamber and Divine Bridge each get a row and
an event flag in **both**, at identical map coordinates. The map drew two pins
on the same pixel, and the Ashen one, which can't be lit until the endgame, sat
on top of the lit one. A place that exists in two versions of one map block is
now a single marker carrying both flags, and counts as found when either is
set. Boss arenas are deliberately left alone: Morgott and Godfrey share the
Erdtree Sanctuary pixel the same way, but killing one must not tick the other.

*Setup silently broke after a game patch.* The extractor caches the decrypted
archive index, which a patch rewrites along with the archives themselves. The
stale cache pointed at the wrong offsets, so every read came back as garbage
and setup died on `not a BND4`. The cache is now invalidated when the game
files are newer than it.

*Clicking a marker did nothing.* `showPopup` declared a local `const t` for the
check-off button, which shadowed the `t()` translate helper for the whole
function and put it in the temporal dead zone — so the first `t('popup.close')`
in the template above it threw `ReferenceError` before `innerHTML` was ever
assigned. No popup had ever opened.

*New: how to get there.* With the popup working, it now also answers the
question you actually have when you click a place. The game's data has no routes
in it and nothing here is hand-written, but the two things you navigate by in
Elden Ring are derivable: the nearest Site of Grace — with whether it's lit, so
you know if you can warp — and the compass direction and distance from it.
Distances are real metres: one map pixel is one world unit. It also shows how
far the place is from your character, saying whether that's your live position
or your last save. Straight-line only, which this game will happily punish you
for.

*Also:* the live-reader badge stayed blank on a fresh page load — the server put
the reader's state in every snapshot, but the client only read it from status
*changes*.

Re-extracting against the patched game picks up six pickups the update added —
the three Spectral Steed Regalia, the Idus Sword, the Ritual Thrusting Shield
and the Reed Great Katana. Nothing else moved.

### 1.2 — map icons
Markers now draw with the game's **own map sprites** — the golden grace ring,
catacomb arches, cave mouths, churches — instead of coloured dots. 89 icons are
extracted from the menu texture sheets; the directional ones (grace rays,
summoning-pool flames) are rotated the way the game draws them. A sidebar
toggle switches back to dots.

Also reads all eight text slots per map point instead of only the first, which
recovers 8 real place names that were showing as "Landmark near X".

### 1.1 — item pickups
**+2,394 item markers**, each tracking its own pickup flag: Golden Seeds, Sacred
Tears, talismans, cookbooks, bell bearings, whetblades, Ashes of War, weapons
and armour. Found by parsing all 864 of the game's MSB map files and joining
them to `ItemLotParam_map`.

**+157 unnamed landmarks** that were previously being dropped — real, flagged
places the game labels with an icon and no text.

Marker total: 949 → 3,508. "Other items" (crafting materials) starts hidden so
it doesn't bury the map.

*Fixes:* overworld LOD tiers were projected at the wrong scale, throwing 17
markers thousands of pixels off the map; Ashes of War resolved against the wrong
name table and silently vanished. The extractor now fails loudly if anything
lands outside the map.

### 1.0 — first release
Live map of The Lands Between and the Realm of Shadow, syncing with your save
file as you play. Four map layers extracted from your own install, 1,114 markers
built from the game's param tables, English and Russian, and an optional
real-time player dot read from the running game.

## Commands

| | |
|---|---|
| `Start Map.bat` | start the map |
| `Start Map LIVE.bat` | start with real-time position (asks for admin) |
| `Check Live Mode.bat` | test whether real-time mode can attach |
| `Setup.bat` | one-time setup, and after game updates |
| `npm start -- --lan` | also serve to your local network |
| `node server/index.js --help` | every server option |

## For the curious

[`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md) covers the interesting parts: how
the save file is decoded, how the map tiles come out of the game archives, and
how world coordinates become map pixels.

### Adding another language

The game ships 13 locales. To add one, e.g. German:

1. Add `"de": "gerde"` to `LOCALES` in `tools/build_markers.py`, then re-run
   `python tools/build_markers.py`.
2. Add a matching `de` block to `STRINGS` and an entry in `LANGS` in
   `web/js/i18n.js`.

Marker names come free from the game — only the UI strings need translating.

Available codes: `jpnjp`, `frafr`, `gerde`, `itait`, `korkr`, `polpl`, `porbr`,
`spaar`, `spaes`, `thath`, `zhocn`, `zhotw`.

## Credits

Built on format documentation from
[ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib),
[SoulsFormats](https://github.com/JKAnderson/SoulsFormats),
[Paramdex](https://github.com/soulsmods/Paramdex),
[EROverlay](https://github.com/soarqin/EROverlay) and
[elden-ring-compass](https://github.com/EthanShoeDev/elden-ring-compass).

Elden Ring is © FromSoftware / Bandai Namco. This is an unaffiliated fan tool.
