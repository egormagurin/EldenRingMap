'use strict';
/**
 * Snapshot recorder. Watches the live save and appends one compact record per
 * change to data/timeline.jsonl. Used to (a) sanity-check the parser against a
 * real play session and (b) learn which flag bits correspond to which in-game
 * events, by diffing consecutive records.
 *
 * Read-only: never writes to the save.
 *   node tools/record.js [savePath]
 */
const fs = require('fs');
const path = require('path');
const { parseSave } = require('../server/lib/saveParser');

/** %APPDATA%/EldenRing/<steamId>/ER0000.sl2 - most recently written. */
function findSave() {
  const appdata = process.env.APPDATA ||
    path.join(require('os').homedir(), 'AppData', 'Roaming');
  const base = path.join(appdata, 'EldenRing');
  let best = null;
  try {
    for (const dir of fs.readdirSync(base)) {
      const p = path.join(base, dir, 'ER0000.sl2');
      try {
        const st = fs.statSync(p);
        if (!best || st.mtimeMs > best.mtimeMs) best = { path: p, mtimeMs: st.mtimeMs };
      } catch { /* not a save dir */ }
    }
  } catch { /* no EldenRing folder */ }
  return best && best.path;
}

const SAVE = process.argv[2] || findSave();
if (!SAVE) {
  console.error('No ER0000.sl2 found. Pass one: node tools/record.js <path>');
  process.exit(1);
}
const OUT = path.join(__dirname, '..', 'data', 'timeline.jsonl');

function setBitIndices(buf) {
  const out = [];
  for (let i = 0; i < buf.length; i++) {
    const b = buf[i];
    if (!b) continue;
    for (let k = 0; k < 8; k++) if (b & (1 << k)) out.push(i * 8 + k);
  }
  return out;
}

function readStable(p, tries = 12) {
  // The game rewrites the file; retry until two consecutive reads agree.
  let prev = null;
  for (let i = 0; i < tries; i++) {
    try {
      const b = fs.readFileSync(p);
      if (prev && prev.length === b.length && prev.equals(b)) return b;
      prev = b;
    } catch { /* mid-write, retry */ }
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 120);
  }
  return prev;
}

let last = null;
let n = 0;

function capture(reason) {
  const buf = readStable(SAVE);
  if (!buf) return;
  let parsed;
  try { parsed = parseSave(buf); } catch (e) { console.error('parse failed:', e.message); return; }
  const c = parsed.characters[0];
  if (!c) return;

  const bits = setBitIndices(c.flagBytes);
  const rec = {
    ts: new Date().toISOString(),
    reason,
    name: c.name,
    level: c.level,
    secondsPlayed: c.secondsPlayed,
    playtimeMs: c.playtimeMs,
    warpSetOffset: c.warpSetOffset,
    warpIds: c.warpIds,
    flagStart: c.flagRegion.start,
    bitCount: bits.length,
    bits,
  };

  if (last) {
    const prevSet = new Set(last.bits);
    const curSet = new Set(bits);
    const added = bits.filter((b) => !prevSet.has(b));
    const removed = last.bits.filter((b) => !curSet.has(b));
    const warpAdded = c.warpIds.filter((w) => !last.warpIds.includes(w));
    if (!added.length && !removed.length && !warpAdded.length &&
        last.level === c.level && last.secondsPlayed === c.secondsPlayed) return;
    rec.diff = { added, removed, warpAdded, dLevel: c.level - last.level,
                 dSeconds: c.secondsPlayed - last.secondsPlayed };
    console.log(`[${rec.ts}] +${added.length} -${removed.length} bits` +
      (warpAdded.length ? `  NEW WARP IDS: ${warpAdded.join(',')}` : '') +
      (rec.diff.dLevel ? `  level +${rec.diff.dLevel} -> ${c.level}` : '') +
      `  (+${rec.diff.dSeconds}s)`);
    if (added.length && added.length <= 40) console.log(`    added bits: ${added.join(',')}`);
  } else {
    console.log(`[${rec.ts}] baseline: ${c.name} lvl ${c.level}, ${bits.length} flag bits, ${c.warpIds.length} warp ids`);
  }

  fs.appendFileSync(OUT, JSON.stringify(rec) + '\n');
  last = rec;
  n++;
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
console.log(`recording ${SAVE}\n     -> ${OUT}`);
capture('baseline');
fs.watchFile(SAVE, { interval: 1000 }, (cur, prev) => {
  if (cur.mtimeMs !== prev.mtimeMs || cur.size !== prev.size) capture('change');
});
setInterval(() => {}, 1 << 30);
