'use strict';
/**
 * Local live-map server for Elden Ring.
 *
 * Watches your save file, decodes it, and pushes progress to the browser over
 * Server-Sent Events. Zero dependencies - Node built-ins only.
 *
 *   node server/index.js [--port 8099] [--save <path to ER0000.sl2>]
 *
 * Read-only: the save is opened for reading and never written.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

const { SaveReader } = require('./lib/saveParser');
const { Projector, TILE_WORLD, OFFSET_X, OFFSET_Y } = require('./lib/project');
const { LiveMemory } = require('./lib/liveMemory');

const ROOT = path.join(__dirname, '..');
const WEB = path.join(ROOT, 'web');
const DATA = path.join(ROOT, 'data');
const USER_STATE = path.join(DATA, 'user-state.json');

/* ------------------------------------------------------------------ config */

function parseArgs(argv) {
  const out = { port: 8099, save: null, poll: 1000, host: '127.0.0.1',
                liveMemory: false, python: 'python', hz: 20 };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--port') out.port = Number(argv[++i]);
    else if (a === '--save') out.save = argv[++i];
    else if (a === '--poll') out.poll = Number(argv[++i]);
    else if (a === '--host') out.host = argv[++i];
    // Bind every interface so phones/tablets on the same Wi-Fi can open it.
    else if (a === '--lan') out.host = '0.0.0.0';
    // Opt-in only: reads the running game for a real-time player dot.
    else if (a === '--live-memory') out.liveMemory = true;
    else if (a === '--python') out.python = argv[++i];
    else if (a === '--hz') out.hz = Number(argv[++i]);
    else if (a === '--help' || a === '-h') out.help = true;
  }
  return out;
}

/**
 * %APPDATA%/EldenRing/<steamId>/ER0000.{err,sl2} - pick the most recent.
 * Elden Ring Reforged saves as ER0000.err, vanilla as ER0000.sl2, and both may
 * be present. Prefer .err when it is at least as recent, so a modded run is not
 * masked by a stale vanilla save.
 */
function findSave() {
  const appdata = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
  const base = path.join(appdata, 'EldenRing');
  const candidates = [];
  try {
    for (const dir of fs.readdirSync(base)) {
      if (!/^\d+$/.test(dir)) continue;
      for (const ext of ['err', 'sl2']) {
        const p = path.join(base, dir, `ER0000.${ext}`);
        try {
          const st = fs.statSync(p);
          if (st.isFile()) candidates.push({ path: p, ext, mtimeMs: st.mtimeMs });
        } catch { /* not present */ }
      }
    }
  } catch { /* no EldenRing folder */ }
  if (!candidates.length) return null;
  candidates.sort((a, b) => b.mtimeMs - a.mtimeMs || (a.ext === 'err' ? -1 : 1));
  return candidates[0].path;
}

/** Every ER0000.* under the same %APPDATA%/EldenRing root, newest first. */
function listSaves(selectedPath) {
  const root = path.dirname(path.dirname(selectedPath));
  const saves = [];
  try {
    for (const account of fs.readdirSync(root)) {
      if (!/^\d+$/.test(account)) continue;
      const accountDir = path.join(root, account);
      for (const file of fs.readdirSync(accountDir)) {
        const match = /^ER0000\.([a-z0-9]+)$/i.exec(file);
        if (!match) continue;
        const savePath = path.join(accountDir, file);
        const stat = fs.statSync(savePath);
        if (!stat.isFile()) continue;
        saves.push({ path: savePath, account, extension: `.${match[1].toLowerCase()}`,
                     mtime: stat.mtimeMs });
      }
    }
  } catch { return []; }
  return saves.sort((a, b) => b.mtime - a.mtime);
}

/** Slot names and levels for the save picker. Best-effort: [] if unreadable. */
function readSaveCharacters(savePath, bst) {
  try {
    const reader = new SaveReader(savePath, bst);
    return reader.read().characters.map((c) => ({ slot: c.slot, name: c.name, level: c.level }));
  } catch { return []; }
}

/* ------------------------------------------------------------------- state */

function loadJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}

const projector = new Projector(loadJson(path.join(DATA, 'legacy-conv.json'), null));

/**
 * Markers come from three generated files: markers.json (graces, bosses, POIs,
 * map fragments - built from the param tables), the optional items.json (item
 * pickups - needs the slower MSB extraction), and the optional pieces.json
 * (Reforged Rune/Ember Piece collectibles). Any of them may be absent.
 */
const markerData = loadJson(path.join(DATA, 'markers.json'), { markers: [] });
const itemData = loadJson(path.join(DATA, 'items.json'), { markers: [] });
const pieceData = loadJson(path.join(DATA, 'pieces.json'), { markers: [] });
const MARKERS = [...(markerData.markers || []), ...(itemData.markers || []),
                 ...(pieceData.markers || [])];
const FLAG_MARKERS = MARKERS.filter((m) => m.flag || (m.flags && m.flags.length));

/**
 * Route descriptions, if the user has fetched them (tools/fetch_tips.py).
 *
 * Optional and deliberately separate: unlike everything else in data/, this
 * text is neither the user's own game files nor ours - it is third-party wiki
 * writing sitting on their disk for their own use. Absent by default, and the
 * app is complete without it.
 */
const tipData = loadJson(path.join(DATA, 'tips.json'), { tips: {} });
const TIPS = tipData.tips || {};
let tipped = 0;
for (const m of MARKERS) {
  const tip = TIPS[m.id];
  if (tip && tip.text) { m.tip = tip; tipped++; }
}

const MARKER_DOC = { locales: markerData.locales || ['en'], markers: MARKERS };

let userState = loadJson(USER_STATE, {});
if (!userState.checked) userState.checked = {};
if (!userState.slots) userState.slots = {};     // save path -> slot on screen last time
function saveUserState() {
  try {
    fs.mkdirSync(DATA, { recursive: true });
    fs.writeFileSync(USER_STATE, JSON.stringify(userState, null, 2));
  } catch (e) { console.error('could not persist user state:', e.message); }
}

/**
 * Marker ids whose event flag is set for this character.
 *
 * A marker can carry several flags. Leyndell, Royal Capital and Leyndell,
 * Ashen Capital are two versions of one map block, so five of its graces exist
 * twice - same pixel, different flag - and build_markers.py folds each pair
 * into a single marker. Any one of the flags means the player has been there.
 */
function computeFound(character) {
  const ef = character._flags;
  if (!ef) return [];
  const found = [];
  for (const m of FLAG_MARKERS) {
    const flags = m.flags || [m.flag];
    if (flags.some((f) => ef.get(f) === true)) found.push(m.id);
  }
  return found;
}

const clients = new Set();
let current = null;      // last good snapshot sent to clients
let live = null;         // optional LiveMemory bridge
let activeSlot = null;   // the slot on screen: picked in the sidebar, or matched to the running game
let slotVotes = {};      // slot -> consecutive wins, for the re-match hysteresis

const hasSlot = (snap, slot) => snap.characters.some((c) => c.slot === slot);

/** The character the browser shows: the active slot, else the first occupied one. */
function shownCharacter(snap) {
  return snap.characters.find((c) => c.slot === activeSlot) || snap.characters[0] || null;
}

/**
 * Show this slot, and remember it for the save so the map reopens on the same
 * character next time. Both the dropdown and the live matcher land here, so
 * "remembered" means whichever character was on screen last.
 */
function setActiveSlot(slot, forPath) {
  activeSlot = slot;
  slotVotes = {};
  if (current) current.activeSlot = slot;
  if (slot === null) delete userState.slots[forPath];
  else userState.slots[forPath] = slot;
  saveUserState();
}

function rememberedSlot(forPath) {
  const slot = userState.slots[forPath];
  return Number.isInteger(slot) ? slot : null;
}

/**
 * Live height, from the player's world position - and the check that decides
 * whether to believe it.
 *
 * The reader cannot tell which of its candidate pointer chains is the right
 * one, so it sends every reading. The map-screen pixel it also sends is already
 * trusted, and in the overworld that pixel is a fixed function of the tile and
 * the block-local x/z:
 *
 *     px = block * 256 + 128 + x + OFFSET_X
 *     py = OFFSET_Y - (mapno * 256 + 128 + z)
 *
 * so inverting it recovers the tile the player is standing on - but only if x
 * and z are genuinely this player's coordinates. A chain pointing at the wrong
 * struct gives numbers that land between tiles, and is rejected. The reading
 * that resolves to whole tiles is the real one, and its y is the height.
 *
 * Legacy dungeons are deliberately not handled: their coordinates are local to
 * the dungeon while the pixel is the translated overworld position, so there is
 * nothing to check against and the save height stands in.
 */
const TILE_EPSILON = 0.01;     // 0.1px of map-screen rounding is ~0.0004 tiles
const TILE_MAX = 80;

function liveHeight(p) {
  if (!p || !Array.isArray(p.worlds) || typeof p.px !== 'number') return null;
  for (const w of p.worlds) {
    const block = (p.px - OFFSET_X - TILE_WORLD / 2 - w.x) / TILE_WORLD;
    const mapno = (OFFSET_Y - p.py - TILE_WORLD / 2 - w.z) / TILE_WORLD;
    const whole = (v) => Math.abs(v - Math.round(v)) < TILE_EPSILON
                      && Math.round(v) >= 0 && Math.round(v) <= TILE_MAX;
    if (whole(block) && whole(mapno)) return Math.round(w.y);
  }
  return null;
}

/**
 * A save holds up to ten characters and the game tells us nothing about which
 * one is loaded. Each character's save position is a good fingerprint though:
 * the running character is the slot whose last saved position is nearest the
 * live one on the same map.
 *
 * Two rules keep one reading from flipping the display for no reason. The
 * slot already on screen keeps its place unless another is nearer by more
 * than a tie margin: two characters resting at the same grace stand on the
 * same spot, so within a few pixels the reading cannot tell them apart, and
 * the one the user picked should not lose to the other on a coin toss. And a
 * reading far from every saved position decides nothing. A character that has
 * never saved has no position at all (the block reads as zeros), and the only
 * alternative would be to hand it to whichever old character is nearest -
 * which is how a brand-new character used to show up as an old one.
 *
 * Returns the slot to show, or null when the reading cannot say.
 */
const SLOT_TIE_PX = 8;        // 1 px is about a metre
const SLOT_MATCH_PX = 1024;   // four tiles: nearer than your last autosave, further than another character

/** The DLC's underground shares the DLC's pixel space (project.js never emits M11). */
const mapFamily = (master) => (master === 'M11' ? 'M10' : master);

function matchActiveSlot(position) {
  if (!current || !position) return null;
  const near = [];
  for (const character of current.characters) {
    const saved = character.mapPixel;
    if (!saved || mapFamily(saved.master) !== mapFamily(position.master)) continue;
    const distance = Math.hypot(saved.px - position.px, saved.py - position.py);
    if (distance <= SLOT_MATCH_PX) near.push({ slot: character.slot, distance });
  }
  if (!near.length) return null;
  near.sort((a, b) => a.distance - b.distance);
  const shown = near.find((c) => c.slot === activeSlot);
  if (shown && shown.distance <= near[0].distance + SLOT_TIE_PX) return activeSlot;
  return near[0].slot;
}

function broadcast(event, payload) {
  const frame = `event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
  for (const res of clients) {
    try { res.write(frame); } catch { clients.delete(res); }
  }
}

function buildSnapshot(reader, savePath) {
  const parsed = reader.read();
  const chars = parsed.characters.map((c) => {
    const found = c.ok ? computeFound(c) : [];
    return {
      slot: c.slot,
      name: c.name,
      level: c.level,
      secondsPlayed: c.secondsPlayed,
      ok: c.ok,
      error: c.error || null,
      stats: c.stats || null,
      position: c.position || null,
      mapPixel: c.position ? projector.project(c.position) : null,
      deaths: c.deaths ?? null,
      lastRestedGrace: c.lastRestedGrace ?? null,
      flagOffset: c.flagOffset ?? null,
      found,
    };
  });
  let mtime = null;
  try { mtime = fs.statSync(savePath).mtimeMs; } catch { /* gone */ }
  return {
    savePath,
    mtime,
    encrypted: parsed.encrypted,
    characters: chars,
    markerCount: MARKERS.length,
    checked: userState.checked,
    live: live ? live.state : { enabled: false, status: 'off' },
    at: Date.now(),
  };
}

/* ----------------------------------------------------------------- watcher */

function startWatcher(reader, savePath, pollMs) {
  let timer = null;
  const refresh = (reason) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      let snap;
      try {
        snap = buildSnapshot(reader, savePath);
      } catch (err) {
        console.error(`[watch] parse failed: ${err.message}`);
        broadcast('error', { message: err.message });
        return;
      }
      const prev = current;
      // The slot on screen can vanish - the character deleted in-game, or the
      // file swapped out underneath us - so fall back rather than keep naming
      // a slot that is no longer in the list.
      if (activeSlot !== null && !hasSlot(snap, activeSlot)) setActiveSlot(null, savePath);
      snap.activeSlot = activeSlot;
      current = snap;

      // Report newly-found markers per character so the UI can highlight them.
      const news = [];
      if (prev) {
        for (const c of snap.characters) {
          const before = prev.characters.find((x) => x.slot === c.slot);
          if (!before) continue;
          const had = new Set(before.found);
          const gained = c.found.filter((id) => !had.has(id));
          if (gained.length) news.push({ slot: c.slot, ids: gained });
        }
      }
      broadcast('state', { ...snap, newlyFound: news });
      const c0 = shownCharacter(snap);
      const label = c0 ? `${c0.name} lv${c0.level} ${c0.found.length}/${FLAG_MARKERS.length}` : 'no character';
      console.log(`[watch] ${reason}: ${label}` +
        (news.length ? `  +${news.reduce((n, x) => n + x.ids.length, 0)} new` : ''));
    }, 350);
  };

  // Returns a stop function rather than `refresh`: switching saves has to tear
  // the old watch down, or both files keep pushing snapshots at the browser.
  const onChange = (cur, prev) => {
    if (cur.mtimeMs !== prev.mtimeMs) refresh('save changed');
  };
  fs.watchFile(savePath, { interval: pollMs }, onChange);
  return () => {
    clearTimeout(timer);
    fs.unwatchFile(savePath, onChange);
  };
}

/* -------------------------------------------------------------- http serve */

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.woff2': 'font/woff2',
};

function serveStatic(req, res, urlPath) {
  const rel = decodeURIComponent(urlPath.replace(/^\/+/, '')) || 'index.html';
  const file = path.join(WEB, rel);
  if (!file.startsWith(WEB)) { res.writeHead(403).end('forbidden'); return; }
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain' }).end('not found');
      return;
    }
    const ext = path.extname(file).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Content-Length': st.size,
      'Cache-Control': ext === '.webp' || ext === '.png' ? 'public, max-age=86400' : 'no-cache',
    });
    fs.createReadStream(file).pipe(res);
  });
}

function json(res, obj, code = 200) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8',
                        'Content-Length': Buffer.byteLength(body) });
  res.end(body);
}

function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    console.log('usage: node server/index.js [options]');
    console.log('  --port <n>      listen port (default 8099)');
    console.log('  --save <path>   ER0000.sl2 to watch (default: auto-detect)');
    console.log('  --lan           also accept connections from your local network');
    console.log('  --host <addr>   bind address (default 127.0.0.1)');
    console.log('  --poll <ms>     save-file poll interval (default 1000)');
    console.log('  --live-memory   also read the running game for a live player dot');
    console.log('                  (read-only, needs admin, falls back silently)');
    console.log('  --hz <n>        live-memory sample rate (default 20)');
    console.log('  --python <exe>  python used for the live reader (default python)');
    return;
  }

  let savePath = args.save || findSave();
  if (!savePath || !fs.existsSync(savePath)) {
    console.error('Could not find ER0000.sl2.');
    console.error('Pass one explicitly:  node server/index.js --save "C:\\path\\to\\ER0000.sl2"');
    process.exit(1);
  }
  const bst = path.join(DATA, 'eventflag_bst.txt');
  if (!fs.existsSync(bst)) {
    console.error(`missing ${bst} - the event-flag block table is required`);
    process.exit(1);
  }
  if (!MARKERS.length) {
    console.warn('warning: data/markers.json is empty - run `python tools/build_markers.py`');
  }

  let reader = new SaveReader(savePath, bst);
  try {
    current = buildSnapshot(reader, savePath);
  } catch (err) {
    console.error('initial save parse failed:', err.message);
    process.exit(1);
  }
  // Reopen on the character that was on screen last time, if it is still there.
  const remembered = rememberedSlot(savePath);
  activeSlot = hasSlot(current, remembered) ? remembered : null;
  current.activeSlot = activeSlot;

  let stopWatcher = () => {};

  /**
   * Point the server at a character: another ER0000.* file, a slot in the
   * current one, or both. The path must be one listSaves() discovered: it
   * arrives from the browser, and the alternative is letting any page on
   * localhost name an arbitrary file for us to open and parse.
   *
   * A null slot means no preference: the slot remembered for that file, if it
   * still exists. The live matcher is not consulted here - its last sample may
   * be minutes old - so the pick stands until fresh readings from the running
   * game say otherwise.
   */
  const switchSave = (nextPath, slot) => {
    let next = current;
    let nextReader = reader;
    if (nextPath !== savePath) {
      const allowed = listSaves(savePath).some((entry) => entry.path === nextPath);
      if (!allowed) throw new Error('save file is outside the discovered Elden Ring profiles');
      nextReader = new SaveReader(nextPath, bst);
      next = buildSnapshot(nextReader, nextPath);   // parse before tearing down
    }
    if (slot === null) {
      const remembered = rememberedSlot(nextPath);
      if (hasSlot(next, remembered)) slot = remembered;
    }
    if (slot !== null && !hasSlot(next, slot)) throw new Error(`no character in slot ${slot}`);
    if (next !== current) {
      stopWatcher();
      savePath = nextPath;
      reader = nextReader;
      current = next;
      stopWatcher = startWatcher(reader, savePath, args.poll);
    }
    setActiveSlot(slot, savePath);
    broadcast('state', { ...current, newlyFound: [] });
  };

  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const p = url.pathname;

    if (p === '/api/state') return json(res, current);
    if (p === '/api/markers') return json(res, MARKER_DOC);

    if (p === '/api/saves' && req.method === 'GET') {
      const saves = listSaves(savePath).map((s) => ({
        ...s,
        characters: readSaveCharacters(s.path, bst),
      }));
      return json(res, { current: savePath, slot: activeSlot, saves });
    }
    if (p === '/api/saves' && req.method === 'POST') {
      let body = '';
      req.on('data', (chunk) => { body += chunk; if (body.length > 65536) req.destroy(); });
      req.on('end', () => {
        try {
          const { path: nextPath, slot } = JSON.parse(body);
          switchSave(nextPath, Number.isInteger(slot) ? slot : null);
          json(res, { ok: true, current: savePath, slot: activeSlot });
        } catch (error) { json(res, { error: error.message }, 400); }
      });
      return undefined;
    }

    if (p === '/api/events') {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
      res.write(': connected\n\n');
      res.write(`event: state\ndata: ${JSON.stringify(current)}\n\n`);
      if (live && live.pos) res.write(`event: pos
data: ${JSON.stringify(live.pos)}

`);
      clients.add(res);
      const ka = setInterval(() => { try { res.write(': ka\n\n'); } catch {} }, 20000);
      req.on('close', () => { clearInterval(ka); clients.delete(res); });
      return undefined;
    }

    if (p === '/api/check' && req.method === 'POST') {
      let body = '';
      req.on('data', (d) => { body += d; if (body.length > 1e6) req.destroy(); });
      req.on('end', () => {
        try {
          const { id, on } = JSON.parse(body || '{}');
          if (typeof id !== 'string') return json(res, { error: 'id required' }, 400);
          if (on) userState.checked[id] = true;
          else delete userState.checked[id];
          saveUserState();
          if (current) current.checked = userState.checked;
          broadcast('checked', { id, on: !!on });
          json(res, { ok: true });
        } catch (e) { json(res, { error: e.message }, 400); }
      });
      return undefined;
    }

    if (p === '/api/refresh') {
      try {
        current = buildSnapshot(reader, savePath);
        current.activeSlot = activeSlot;
        broadcast('state', { ...current, newlyFound: [] });
        return json(res, { ok: true });
      } catch (e) { return json(res, { error: e.message }, 500); }
    }

    return serveStatic(req, res, p);
  });

  stopWatcher = startWatcher(reader, savePath, args.poll);

  if (args.liveMemory) {
    live = new LiveMemory({
      root: ROOT, python: args.python, hz: args.hz,
      onPos: (p) => {
        // Re-match on every sample, but require three consecutive wins before
        // switching. Two characters resting at the same grace, or a frame taken
        // mid-loading-screen, would otherwise flip the displayed character on a
        // single bad reading. It also self-corrects a wrong first match.
        const matched = matchActiveSlot(p);
        if (matched !== null) {
          if (matched !== activeSlot) {
            slotVotes[matched] = (slotVotes[matched] || 0) + 1;
            if (slotVotes[matched] >= 3) setActiveSlot(matched, savePath);
          } else {
            slotVotes = {};
          }
        }
        p.slot = activeSlot;
        const h = liveHeight(p);
        if (h !== null) p.h = h;
        delete p.worlds;          // candidate readings are server-side plumbing
        if (current) current.activeSlot = activeSlot;
        broadcast('pos', p);
      },
      onStatus: (st) => { if (current) current.live = st; broadcast('live', st); },
    });
    live.start();
  }

  server.listen(args.port, args.host, () => {
    const c = shownCharacter(current);
    console.log('');
    console.log('  Elden Ring live map');
    console.log(`  save      ${savePath}`);
    console.log(`  markers   ${MARKERS.length} (${FLAG_MARKERS.length} flag-tracked)` +
      (itemData.markers && itemData.markers.length
        ? `  incl. ${itemData.markers.length} items` : '  (no items.json - run tools/extract_items.py)') +
      (pieceData.markers && pieceData.markers.length
        ? `, ${pieceData.markers.length} pieces` : ''));
    if (tipped) {
      console.log(`  tips      ${tipped} route descriptions` +
        (tipData.credit ? ` via ${tipData.credit}` : ''));
    }
    if (c) {
      console.log(`  character ${c.name}, level ${c.level}, ` +
        `${Math.floor(c.secondsPlayed / 3600)}h${String(Math.floor(c.secondsPlayed % 3600 / 60)).padStart(2, '0')}m` +
        `  -> ${c.found.length} found`);
    }
    if (args.liveMemory) {
      console.log('  live      real-time position from the running game (read-only)');
    }
    console.log('');
    console.log(`  open  http://localhost:${args.port}`);
    if (args.host === '0.0.0.0') {
      for (const [, addrs] of Object.entries(os.networkInterfaces())) {
        for (const a of addrs || []) {
          if (a.family === 'IPv4' && !a.internal) {
            console.log(`  LAN   http://${a.address}:${args.port}`);
          }
        }
      }
    }
    console.log('');
  });
}

main();
