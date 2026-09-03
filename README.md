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
  item pickups** sorted into **47 categories**, each with its own icon: Golden
  Seeds, Crystal Tears, talismans, spirit ashes, cookbooks, bell bearings,
  whetblades, smithing stones by tier, golden runes by tier, gloveworts,
  incantations, sorceries, weapons and armour.
- **The game's own map icons** — graces, catacombs, caves, churches and the rest
  are drawn with the real sprites lifted out of the game, not coloured dots.
- **Live progress.** Found markers turn green, and a popup names whatever you
  just discovered. Progress bars per category.
- **How high up is it.** Hover or click any marker for its height, which is the
  thing you actually want on a 2D map of a very vertical game — the Forge of the
  Giants reads 1969 m, the bottom of the Siofra River well −482 m. Your own
  height sits in the Character panel to compare against, live as you move.
- **Your character** — level, playtime, deaths and all eight stats.
- **Real-time position** (optional) — a dot that moves as you move.
- **English and Russian**, using the game's own text for every marker name.
- **Follow mode** — the ◎ button latches, so the map keeps itself centred on you
  as you ride.
- **Elden Ring Reforged**, if you play it: the mod's own items and its Rune and
  Ember Pieces, read from the mod's files.
- Search, marker clustering, manual check-off, and a "hide found" filter.
- Categories toggle independently, so you can show just Golden Seeds, or just
  what you haven't picked up yet — and the sidebar remembers your choices,
  folded panels, map layer and character between sessions.

---

## Requirements

| | |
|---|---|
| OS | Windows 10/11, or Linux with Steam Proton |
| Elden Ring | installed — the map art is read out of your install |
| [Node.js](https://nodejs.org) | 18 or newer (LTS is fine) |
| [Python](https://python.org) | 3.9 or newer — **tick "Add Python to PATH"** in the installer |

About 65 MB of disk for the generated map tiles and icons.

The setup scripts check all of this before doing any work and say exactly what
is missing, so you don't find out three minutes in. On Linux they also need
`git`, `cmake` and a C++ compiler to build the Oodle shim — if any are absent
you get the install command for your distro. `uv` and `clang` are used when
present but are not required.

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

### Playing Elden Ring Reforged?

Set `MODDIR` in `Setup.bat` as well, to the mod folder holding its own
`regulation.bin`:

```bat
set MODDIR=D:\Games\ELDEN RING Reforged\mod
```

Setup then reads the mod's params, map files, text and icons over the game's
archives, and adds the mod's Rune and Ember Piece markers. Map tiles still come
from the base game unless the mod replaces them. Leave `MODDIR` empty for a
normal unmodded game — there are no pieces to find in one.

### Linux with Steam Proton

There are native launchers, no Wine needed for the extraction step:

```bash
./setup-linux.sh
./start-map.sh
```

`setup-linux.sh` builds a native Oodle shim against the game's own
`oo2core_6_win64.dll`, and `start-map.sh` reads the running Proton process
through `/proc` for real-time position — it does not depend on a particular
Proton build.

It needs `git`, `cmake`, a C++ compiler, Python 3.9+ and Node 18+. Run
`./setup-linux.sh --check` first and it lists anything missing with the install
command for your distro. [`uv`](https://docs.astral.sh/uv/) and `clang` are used
if you have them and quietly skipped if you don't.

Paths are auto-detected from `$HOME`; override any of them with `ER_GAME_DIR`,
`ER_STEAM_ROOT`, `ER_MOD_DIR`, `ER_PREFIX` or `ER_SAVE`. Pass the Reforged mod
folder the same way:

```bash
ER_MOD_DIR="/path/to/ERR/mod" ./setup-linux.sh
```

---

## Using it

**Double-click `Start Map.bat`.** Your browser opens at
`http://localhost:8099`. Leave the black console window open while you play —
closing it stops the map.

Your save is found automatically. Start the game, play, and the map keeps up on
its own.

If you have more than one character, the sidebar has two dropdowns: one for the
save type (`.sl2` for vanilla, `.err` for Reforged) and one listing every
character in every save of that type, by name and level. Pick one and the map
shows that character's progress. The choice is remembered, so the map reopens on
the same character next time. With real-time mode on, the running character
takes over by itself.

| Control | |
|---|---|
| Drag | pan |
| Scroll / double-click | zoom |
| Hover a marker | its name, category and height |
| Click a marker | details and a manual check-off button |
| `/` | jump to search |
| `Esc` | close popups |
| ◎ button | follow your character — click again, or drag, to stop |

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

On Windows there is a second cause worth knowing about. Windows ships a
zero-byte placeholder for `python.exe` whose only job is to open the Microsoft
Store, and it sits on your PATH whether or not you have Python. Anything that
merely checks "is python on the PATH" is fooled by it. The scripts here run
Python instead of looking for it, so they see through the placeholder and fall
back to the `py` launcher if that works — but it is why `where python` can
succeed on a machine with no Python at all.

### "Your Python is too old" / "Your Node.js is too old"

Python must be 3.9+ and Node 18+. The scripts print the version they found.
Install a current one, then open a *new* console.

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

### The wrong character is shown

Pick the right one from the **Character** dropdown in the sidebar. It lists
every character in every save, and the map remembers the choice.

With real-time mode on, the running character is matched to a save slot by
comparing its live position against each slot's last saved position, and takes
over from whatever you picked within a few samples of you moving. A character
that has never saved has no position to match yet — the slot reads as zeros
until its first autosave — so a brand-new character stays on the dropdown
choice until then. Without a running game there is nothing to compare against,
and the dropdown choice (or the first occupied slot) is shown.

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

### A boss marker says "Boss arena near …"

That's the honest fallback for the 19 arenas whose name couldn't be recovered.
189 of 208 carry the enemy's real name; the rest say which place they're beside
rather than pretending to be named after it.

One known miss: the Deeproot Depths arena reads "Sorcerer Rogier / Fia's
Champion". Rogier is summonable there, and his name sits close enough to the
boss's in the event script to be picked up too.

---

## Known limitations

- **Which character is shown** is guessed from position when real-time mode is
  on, and is otherwise the first occupied slot. You can change the save *file*
  from the sidebar, but not the slot within it.
- **The item categories follow the Reforged item ids.** On a vanilla game a
  handful of items — the drawstring greases, the DLC's Spectral Steed Regalia —
  land in "Other items" instead of their own category.
- **Not every item is placed.** 2,400 pickups come from the game's map files;
  some others are spawned by event scripts and aren't covered. Enemy drops are
  not included either.
- **Shadow of the Erdtree items are missing.** The base game ships the DLC's map
  art and text, so the DLC map layer and its graces/bosses do appear — but the
  DLC's own map files are only present if you own and have installed it.
- **19 of 208 boss arenas have no recoverable name**, as above.
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

### 1.8 — pick your character

**A second character in the same save could not be selected.** The save-file
dropdown named a file by every character inside it — `Tarnished · Level 57 /
Wretch · Level 6` was one entry — and the map always showed the first occupied
slot. Real-time mode did not rescue it: the running character is matched to a
slot by comparing the live position against each slot's last saved position,
and a character that has never saved has no position at all (the block reads as
zeros), so a brand-new one was skipped and its dot was handed to whichever old
character was nearest.

The dropdown is now one entry per character — name and level, across every
save of the chosen type — and picking one shows that character's progress,
stats and position. The choice is remembered per save file, so the map reopens
on the same character.

**Live matching now respects the pick.** The slot on screen keeps its place
unless another slot's saved position is nearer by more than 8 px: two
characters resting at the same grace stand on the same spot, and used to
resolve to whichever came first in the file. And a reading more than four
tiles from every saved position decides nothing, rather than defaulting to the
nearest stranger — which covers a fresh character before its first autosave,
and you on Torrent between two of them. Once the running character has saved,
it is the one shown, whatever the dropdown said.

### 1.7 — Farum Azula lands on its own map

**Crumbling Farum Azula had no markers.** All 102 of them — every grace, both
bosses, 86 item pickups — were sitting 2,547 px away in the Mountaintops of the
Giants, beside the Forge of the Giants, while the floating island the game draws
out east stayed empty.

Legacy dungeons are translated onto the overworld through
`WorldMapLegacyConvParam`, and a dungeon that straddles several overworld cells
gets one row per cell. For 95 of the 98 blocks those rows all describe the same
world point in a different cell-local frame, so choosing between them by nearest
source anchor is harmless. Farum Azula is one of the three where it is not: its
four rows disagree by up to 3,673 px, because the island is drawn nowhere near
where it connects to the overworld. The nearest anchor was the row that says
Farum Azula's origin *is* the Forge of the Giants — true of the way in, useless
for the map — and it won for 101 of the 102 markers. The row the game itself
flags as the base point puts them on the island.

The row is now picked once per block instead of once per marker, so a region
cannot be split across two places: overworld destination first, then the game's
own `isBasePoint`, then whichever row spells an anchor out rather than leaving it
at the origin. The live projector picks the same way, so the player dot follows.

**Metyr, Mother of Fingers** was 912 px from her own arena for the same reason.
She sits on the Finger Birthing Grounds now, where she lives. The Haligtree's
rows disagree too, by 661 px, but were already landing on the right one.

**Farum Azula's heights changed.** Height rides the same translation chain as
the horizontal axes, so it moved with them: Dragonlord Placidusax reads 2228 m
rather than 1010, Maliketh 1185 rather than −33. The new numbers are the
consistent ones — the old ones came from the anchor that had the markers in the
wrong place.

**Re-run setup** (or `python tools/build_markers.py` and
`python tools/extract_items.py`) — marker positions come from the generated
files, so Farum Azula stays empty until they are rebuilt.

### 1.6 — the sidebar remembers itself

**Collapsing the sidebar broke the map.** The collapsed rule pulled the sidebar
`margin-left: -320px` *and* set its width to zero, which counts the collapse
twice: the sidebar then contributed −320px to the flex line, so the map became
320px wider than the window and started at x=−320. Its left edge ran off-screen,
and the ⟩ tab that brings the sidebar back went with it — which is why there
appeared to be no way to reopen it. It slides now, and nothing else.

**The map stretched.** The canvas backing store only followed the *window*
resizing, so collapsing the sidebar grew its CSS box while the bitmap kept its
old pixel size and the browser scaled it up over the gap. It follows its own box
now, through a `ResizeObserver`.

**The sidebar remembers.** Which categories are on, the three option checkboxes,
which panels you folded away, whether the sidebar itself is collapsed, and the
map layer all persist in `localStorage`. A category introduced by a later version
takes its own default rather than being silently switched off because an older
saved list did not mention it, and unreadable or unavailable storage falls back
to the defaults instead of failing.

### 1.5 — marker height

Clicking a marker used to answer "how do I get there": the nearest Site of
Grace, whether it was lit, and the bearing and distance from it and from your
character. It answers "how high is it" instead now — one number, the way Map
for Goblins does it.

Height is the useful axis here. The map is flat and the game is not: two markers
a few pixels apart can be a cliff, a lift and a fifteen-minute detour apart, and
a straight-line bearing quietly implied otherwise.

The extractors now carry the world Y through the same translation chain as the
horizontal axes, so heights are comparable across maps — the Forge of the Giants
reads 1969 m, the bottom of the Siofra River well −482 m, Godrick's grace and
his arena 348 m and 347 m. Map fragments have no height and simply omit the row:
they are the centre of the region a fragment reveals, not a thing standing
anywhere.

The height shows in the tooltip on hover as well as in the popup, and your own
height sits in the Character panel so a marker's number means something without
doing arithmetic.

Your height is live in real-time mode. The map screen the reader samples has no
vertical axis, so this reads the player's world position out of `WorldChrMan`
instead — and rather than trusting a pointer chain that moves between game
versions, the reader sends every candidate reading and the server keeps only one
that agrees with the map-screen pixel it already trusts. In the overworld that
pixel is a fixed function of the tile and your local x/z, so inverting it
recovers a whole-numbered tile only when the coordinates are genuinely yours. A
chain that is wrong, or that a patch has moved, produces no height rather than a
confident wrong one, and your last-saved height stands in. `Check Live Mode.bat`
shows which chain matched.

Inside legacy dungeons the coordinates are dungeon-local while the pixel is the
translated overworld position, so there is nothing to check against and the
save height is used there too.

**Re-run setup** (or `python tools/build_markers.py` and
`python tools/extract_items.py`) — marker heights come from the generated files,
so existing ones show no height until they are rebuilt.

### 1.4 — item categories, mod support, Linux

**47 item categories instead of 11.** Item markers were sorted by name
heuristics into a handful of buckets, with everything else — about 1,900
markers — dumped into "Other items". They are now classified by item id
against [Map for Goblins](https://github.com/VirusAlex/ERR-MapForGoblins-DLL)'
tables: smithing stones and golden runes split by tier, crystal tears,
gloveworts, incantations, sorceries, spirit ashes, greases, throwables,
prattling pates, and the rest. "Other items" is down to 36 markers. Each
category carries its own icon, on the map and in the sidebar.

**Elden Ring Reforged.** Set `MODDIR` in `Setup.bat` (or `ER_MOD_DIR`) and the
extractors read the mod's `regulation.bin`, map files, text and icon atlases
over the game's archives. Its Rune and Ember Pieces are placed too — they are
MSB entities rather than treasure lots, so `tools/extract_pieces.py` handles
them separately. The server picks up `ER0000.err` saves as well as `.sl2`.

**Native Linux.** `setup-linux.sh` and `start-map.sh` run the whole thing on
Steam Proton, building an Oodle shim against the game's own DLL so extraction
needs no Wine, and reading the live position out of `/proc`.

**Follow mode.** The ◎ button latches instead of jumping once: the map keeps
re-centring on you as you ride, and switches layer when you cross between the
surface and the Underground. Click it again or drag the map to release it.
Zooming does not.

**Save and character picking.** The sidebar lists every `ER0000.*` it can find,
labelled by the characters inside rather than a Steam account id, and switching
between them re-reads without a restart. With real-time mode on, the running
character is matched to its save slot by position — three consecutive samples
have to agree before it switches, so a shared grace or a loading screen cannot
flip it.

**Collapsible sidebar.** Every section folds by its header, and the whole
sidebar folds away to a tab so the map gets the full window.

Ported from [xizha127's fork](https://github.com/xizha127/EldenRingMap), with
thanks.

### 1.3 — real boss names

Boss markers used to borrow the name of the nearest Site of Grace, because
`GameAreaParam` has positions and defeat flags but no name field. 194 of 208
were named after something that wasn't the boss, 83 shared a name with another
marker, and 14 were just "Boss arena (12_01)".

**189 of 208 now carry the enemy's actual name**, in the game's own English and
Russian. The name isn't in the params at all — the game sets it when it draws
the health bar, from an event script — but decompiling EMEVD turned out to be
unnecessary. That call passes the boss's entity id and its `NpcName` text id in
the same argument blob a few words apart, and both are exact values already
known: the entity id equals the defeat flag, and the text id has to be a live
`NpcName` key. Scanning a 16-byte window around each defeat flag either finds
the right name or finds nothing.

Fights with more than one name keep all of them, in phase order —
`Beast Clergyman / Maliketh, the Black Blade`, `Radagon of the Golden Order /
Elden Beast`, `Crystalian (Staff) / Crystalian (Spear)`. The remaining 19 say
"Boss arena near <place>" instead of impersonating a grace.

This does **not** give boss *prerequisites* — those live in the event script
logic, which would need real decompilation. But a marker reading "Night's
Cavalry" rather than "Warmaster's Shack" already tells you why it isn't there in
daylight.

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
for. (Replaced in 1.5 by the marker height.)

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

Item categories, their icons, and the Rune/Ember Piece locations come from
[Map for Goblins](https://github.com/VirusAlex/ERR-MapForGoblins-DLL) by
VirusAlex, MIT-licensed — see `web/icons/categories/NOTICE.txt`. The Linux
Oodle shim is [linoodle](https://github.com/McSimp/linoodle) by McSimp. Linux
support and the Map-for-Goblins integration were ported from
[xizha127's fork](https://github.com/xizha127/EldenRingMap).

Elden Ring is © FromSoftware / Bandai Namco. This is an unaffiliated fan tool.
