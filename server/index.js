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
const { Projector } = require('./lib/project');
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
const MARKER_DOC = { locales: markerData.locales || ['en'], markers: MARKERS };

let userState = loadJson(USER_STATE, { checked: {} });
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
let activeSlot = null;   // which save slot the running character is in
let slotVotes = {};      // slot -> consecutive wins, for the re-match hysteresis

/**
 * A save holds up to ten characters and the game tells us nothing about which
 * one is loaded. Each character's save position is a good fingerprint though:
 * the running character is the slot whose last saved position is nearest the
 * live one on the same map. Ties resolve themselves as soon as you move.
 */
function matchActiveSlot(position) {
  if (!current || !position) return null;
  let best = null;
  for (const character of current.characters) {
    const saved = character.mapPixel;
    if (!saved || saved.master !== position.master) continue;
    const distance = Math.hypot(saved.px - position.px, saved.py - position.py);
    if (!best || distance < best.distance) best = { slot: character.slot, distance };
  }
  return best && best.slot;
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
      const c0 = snap.characters[0];
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

  let stopWatcher = () => {};

  /**
   * Point the server at another ER0000.* file. The path must be one listSaves()
   * discovered: it arrives from the browser, and the alternative is letting any
   * page on localhost name an arbitrary file for us to open and parse.
   */
  const switchSave = (nextPath) => {
    const allowed = listSaves(savePath).some((entry) => entry.path === nextPath);
    if (!allowed) throw new Error('save file is outside the discovered Elden Ring profiles');
    const nextReader = new SaveReader(nextPath, bst);
    const next = buildSnapshot(nextReader, nextPath);   // parse before tearing down
    stopWatcher();
    savePath = nextPath;
    reader = nextReader;
    activeSlot = null;
    slotVotes = {};
    current = next;
    if (live && live.pos) activeSlot = matchActiveSlot(live.pos);
    current.activeSlot = activeSlot;
    current.live = live ? live.state : null;
    stopWatcher = startWatcher(reader, savePath, args.poll);
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
      return json(res, { current: savePath, saves });
    }
    if (p === '/api/saves' && req.method === 'POST') {
      let body = '';
      req.on('data', (chunk) => { body += chunk; if (body.length > 65536) req.destroy(); });
      req.on('end', () => {
        try {
          switchSave(JSON.parse(body).path);
          json(res, { ok: true, current: savePath });
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
            if (slotVotes[matched] >= 3) {
              activeSlot = matched;
              slotVotes = {};
            }
          } else {
            slotVotes = {};
          }
        }
        p.slot = activeSlot;
        if (current) current.activeSlot = activeSlot;
        broadcast('pos', p);
      },
      onStatus: (st) => { if (current) current.live = st; broadcast('live', st); },
    });
    live.start();
  }

  server.listen(args.port, args.host, () => {
    const c = current.characters[0];
    console.log('');
    console.log('  Elden Ring live map');
    console.log(`  save      ${savePath}`);
    console.log(`  markers   ${MARKERS.length} (${FLAG_MARKERS.length} flag-tracked)` +
      (itemData.markers && itemData.markers.length
        ? `  incl. ${itemData.markers.length} items` : '  (no items.json - run tools/extract_items.py)') +
      (pieceData.markers && pieceData.markers.length
        ? `, ${pieceData.markers.length} pieces` : ''));
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
