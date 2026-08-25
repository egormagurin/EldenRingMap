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
- **3,500 markers that track themselves** — 418 Sites of Grace, 208 boss arenas,
  289 points of interest, 165 unnamed landmarks, 34 map fragments, and **2,389
  item pickups**: Golden Seeds, Sacred Tears, talismans, cookbooks, bell
  bearings, whetblades, weapons and armour.
- **Live progress.** Found markers turn green, and a popup names whatever you
  just discovered. Progress bars per category.
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

About 65 MB of disk for the generated map tiles.

---

## Setup — once, about two minutes

**1. Get the files**

```bash
git clone https://github.com/egormagurin/EldenRingMap.git
cd EldenRingMap
```

**2. Run `Setup.bat`**

Double-click it. It finds your Elden Ring install, installs a few Python
packages, extracts the map tiles, builds the marker list, and reads all 864 of
the game's map files to find where every item is. You only need to do this again
after a game update.

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
| Click a marker | details, plus a manual check-off button |
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
- **Not every item is placed.** 2,389 pickups come from the game's map files;
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
