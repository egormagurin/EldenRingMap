'use strict';
/**
 * Elden Ring live map — client.
 *
 * Talks to the local server: markers + tile manifest once, then a Server-Sent
 * Events stream that pushes a fresh snapshot every time the save file changes.
 */

// Labels come from i18n ('cat.<key>'); only presentation lives here.
// Order here is the order shown in the sidebar: world markers from
// build_markers.py first, then the item categories from extract_items.py.
//
// `icon` is a PNG basename under web/icons/categories/ (Map for Goblins' own
// icons, MIT - see the NOTICE there). The markers themselves carry their icon
// in the generated JSON; this copy is what the sidebar swatch draws.
const CATS = {
  grace:     { color: '#ffd766', r: 6 },
  boss:      { color: '#e05a5a', r: 6 },
  poi:       { color: '#6fb7e8', r: 5 },
  region:    { color: '#9aa0a8', r: 5 },
  fragment:  { color: '#c58bea', r: 5 },
  landmark:  { color: '#8fa3b8', r: 4 },
  // --- equipment ---
  armaments:    { color: '#d4805a', r: 4, icon: 'weapon.png' },
  armour:       { color: '#a08f76', r: 4, icon: 'armor.png' },
  ashes_of_war: { color: '#b58bea', r: 4, icon: 'ash.png' },
  spirits:      { color: '#8be8d0', r: 4, icon: 'spirit.png' },
  talismans:    { color: '#e8b84a', r: 4, icon: 'talisman.png' },
  // --- key items ---
  celestial_dew:      { color: '#aed8ff', r: 4, icon: 'dew.png' },
  cookbooks:          { color: '#d9c89a', r: 4, icon: 'cookbook.png' },
  crystal_tears:      { color: '#7dd0ff', r: 4, icon: 'crystal_tears.png' },
  imbued_sword_keys:  { color: '#b0c4ff', r: 4, icon: 'stone_key_2.png' },
  larval_tears:       { color: '#ff9dd6', r: 4, icon: 'larval.png' },
  lost_ashes:         { color: '#cf9fe8', r: 4, icon: 'lost_ash.png' },
  pots_n_perfumes:    { color: '#c9b58a', r: 4, icon: 'pots_n_perfumes.png' },
  seeds_tears:        { color: '#8ede7a', r: 4, icon: 'seed.png' },
  scadutree_fragments:{ color: '#e8d8a0', r: 4, icon: 'skadu.png' },
  whetblades:         { color: '#c9c9c9', r: 4, icon: 'whetblade.png' },
  great_runes:        { color: '#ffd766', r: 4, icon: 'great.png' },
  // --- loot ---
  ammo:                  { color: '#c9a06a', r: 4, icon: 'ammo.png' },
  bell_bearings:         { color: '#e0a35a', r: 4, icon: 'bell.png' },
  merchant_bell_bearings:{ color: '#d88a4a', r: 4, icon: 'bell_m.png' },
  consumables:           { color: '#9fbf8f', r: 3, icon: 'consumables.png' },
  greases:               { color: '#c9d17a', r: 3, icon: 'grease.png' },
  utilities:             { color: '#8fb8a8', r: 3, icon: 'utils.png' },
  stat_boosts:           { color: '#d8a8c8', r: 3, icon: 'shard.png' },
  crafting_materials:    { color: '#7fae7f', r: 3, icon: 'materials.png' },
  gloveworts:            { color: '#c9b5d8', r: 3, icon: 'glove.png' },
  great_gloveworts:      { color: '#a890c9', r: 3, icon: 'glove_high.png' },
  golden_runes:          { color: '#e8d04a', r: 4, icon: 'rune_high.png' },
  golden_runes_low:      { color: '#d8c040', r: 3, icon: 'rune_low.png' },
  material_nodes:        { color: '#7fae7f', r: 3, icon: 'nodes.png' },
  mp_fingers:            { color: '#c9a8a8', r: 3, icon: 'finger.png' },
  prattling_pates:       { color: '#e0c8a0', r: 3, icon: 'pate.png' },
  gestures:              { color: '#c0c9d8', r: 3, icon: 'gesture.png' },
  reusables:             { color: '#a8c9c0', r: 3, icon: 'reusable.png' },
  smithing_stones:       { color: '#d8b878', r: 4, icon: 'smst.png' },
  smithing_stones_low:   { color: '#c9a868', r: 3, icon: 'smst_low.png' },
  smithing_stones_rare:  { color: '#e0c890', r: 4, icon: 'smst_high.png' },
  stonesword_keys:       { color: '#b0c0e0', r: 4, icon: 'stone_key.png' },
  throwables:            { color: '#c9a0a0', r: 3, icon: 'throw.png' },
  rune_arcs:             { color: '#e8d878', r: 4, icon: 'ark.png' },
  dragon_hearts:         { color: '#e08080', r: 4, icon: 'dragon_heart.png' },
  // --- magic ---
  incantations:  { color: '#e8b878', r: 4, icon: 'incantation.png' },
  memory_stones: { color: '#c9b8e0', r: 4, icon: 'memory.png' },
  prayerbooks:   { color: '#d8c8a0', r: 4, icon: 'prayerbook.png' },
  sorceries:     { color: '#8bb8e8', r: 4, icon: 'sorceries.png' },
  // --- quest ---
  deathroot:      { color: '#c08080', r: 4, icon: 'death.png' },
  progression:    { color: '#c0a8d8', r: 4, icon: 'quest.png' },
  seedbed_curses: { color: '#a080c0', r: 4, icon: 'curse.png' },
  // --- Elden Ring Reforged only ---
  ember_pieces:      { color: '#ff8a5a', r: 4, icon: 'ember_piece.png' },
  items_and_changes: { color: '#d8a8e0', r: 4, icon: 'reforged.png' },
  fortunes:          { color: '#e8c080', r: 4, icon: 'fortune.png' },
  rune_pieces:       { color: '#ffd080', r: 4, icon: 'rune_piece.png' },
  sealed_curios:     { color: '#b8a8d8', r: 4, icon: 'curio.png' },
  // --- fallback ---
  misc: { color: '#6f6f6f', r: 3 },
};

// High-volume categories that bury the map when they are all on at once. They
// start hidden and can be switched on from the sidebar.
const OFF_BY_DEFAULT = new Set(['misc', 'consumables', 'crafting_materials', 'ammo']);
const FOUND_COLOR = '#6fcf7a';

const $ = (id) => document.getElementById(id);
const t = (k) => I18n.t(k);
const nameOf = (m) => I18n.name(m);
const catLabel = (k) => t('cat.' + k);

const state = {
  markers: [],
  byId: new Map(),
  manifest: null,
  master: 'M00',
  enabled: new Set(Object.keys(CATS).filter((k) => !OFF_BY_DEFAULT.has(k))),
  found: new Set(),
  checked: {},
  hideFound: false,
  showLabels: true,
  saves: [],            // every ER0000.* the server found, from api/saves
  savePath: null,       // the one it is currently watching
  characters: [],       // every slot in that save
  character: null,      // the slot being displayed
  selected: null,
  hovered: null,
  clusters: [],
  livePos: null,        // newest sample from the memory reader
  liveStatus: null,     // 'live' | 'waiting' | 'error' | ...
  playerRender: null,   // eased toward livePos so the dot glides
  icons: null,          // iconId -> {file,w,h}, from web/icons/index.json
  iconImgs: new Map(),  // icon key -> HTMLImageElement, loaded lazily
  showIcons: true,      // draw real sprites instead of coloured dots
  followPlayer: false,  // keep re-centring on the player until told to stop
};

/** Load an icon once, redrawing when it arrives; null until it is ready. */
function loadIcon(key, src) {
  let img = state.iconImgs.get(key);
  if (img === undefined) {
    img = new Image();
    img.decoding = 'async';
    img.onload = () => { if (map) map.requestDraw(); };
    img.onerror = () => state.iconImgs.set(key, null);
    img.src = src;
    state.iconImgs.set(key, img);
  }
  return img && img.complete && img.naturalWidth ? img : null;
}

/**
 * Marker sprites, from two sources that the marker's `icon` field distinguishes
 * by shape. World markers carry a numeric iconId cut out of the game's own
 * atlases by tools/extract_icons.py and resolved through icons/index.json; item
 * markers carry a PNG basename served straight from icons/categories/. Both are
 * optional - without either, markers fall back to coloured dots.
 */
function iconFor(mk) {
  if (!state.showIcons || !mk.icon) return null;
  const key = mk.icon;
  if (typeof key === 'string' && key.endsWith('.png')) {
    const img = loadIcon(key, 'icons/categories/' + key);
    return img ? { img, meta: { w: img.naturalWidth, h: img.naturalHeight } } : null;
  }
  if (!state.icons) return null;
  const meta = state.icons[key];
  if (!meta) return null;
  const img = loadIcon(key, meta.file);
  return img ? { img, meta } : null;
}

let map = null;

/* --------------------------------------------------------------- boot */

async function boot() {
  I18n.init();
  I18n.apply();
  buildLangSwitch();

  const [manifest, markerDoc, iconDoc, saveDoc] = await Promise.all([
    fetch('tiles/manifest.json').then((r) => r.json()).catch(() => null),
    fetch('api/markers').then((r) => r.json()).catch(() => ({ markers: [] })),
    fetch('icons/index.json').then((r) => r.json()).catch(() => null),
    fetch('api/saves').then((r) => r.json()).catch(() => ({ current: null, saves: [] })),
  ]);
  state.icons = iconDoc && iconDoc.icons ? iconDoc.icons : null;

  state.manifest = manifest;
  state.markers = (markerDoc.markers || []).filter((m) => m.px != null);
  state.saves = saveDoc.saves || [];
  state.savePath = saveDoc.current || null;
  for (const m of state.markers) state.byId.set(m.id, m);

  if (!manifest || !manifest.masters || !Object.keys(manifest.masters).length) {
    $('foot').textContent = t('app.noTiles');
  }

  buildLayerButtons();
  buildCategories();
  initMap(state.master);
  wireUi();
  buildSavePicker();
  connect();

  // Language changes only ever affect text, so nothing needs reloading.
  I18n.onChange(() => {
    buildLangSwitch();
    buildLayerButtons();
    buildCategories();
    refreshCounts();
    if (state.character) renderCharacter(state.character);
    if (state.selected) {
      const m = state.byId.get(state.selected);
      if (m) showPopup(m);
    }
    $('toggle-all').textContent = state.enabled.size ? t('panel.selectNone') : t('panel.selectAll');
    if (map) map.requestDraw();
  });
}

function buildLangSwitch() {
  const wrap = $('lang-switch');
  wrap.innerHTML = '';
  for (const l of window.I18N_LANGS) {
    const b = document.createElement('button');
    b.className = 'lang-btn' + (l.code === I18n.lang ? ' active' : '');
    b.textContent = l.code.toUpperCase();
    b.title = l.label;
    b.onclick = () => I18n.set(l.code);
    wrap.appendChild(b);
  }
}

function masterInfo(id) {
  return (state.manifest && state.manifest.masters && state.manifest.masters[id]) || null;
}

function tileIndexFor(id) {
  const info = masterInfo(id);
  if (!info || !info.tiles) return null;
  const out = {};
  for (const z of Object.keys(info.tiles)) {
    out[z] = new Set(info.tiles[z].map((p) => p[0] + ',' + p[1]));
  }
  return out;
}

function initMap(masterId) {
  const info = masterInfo(masterId);
  const fmt = (state.manifest && state.manifest.format) || 'webp';
  const canvas = $('map');
  if (map) { map.canvas.replaceWith(canvas.cloneNode()); }

  map = new TileMap($('map'), {
    tileSize: (state.manifest && state.manifest.tileSize) || 256,
    width: info ? info.width : 10496,
    height: info ? info.height : 10496,
    nativeZoom: info ? info.nativeZoom : 6,
    tileIndex: tileIndexFor(masterId),
    tileUrl: (z, x, y) => `tiles/${masterId}/${z}/${x}/${y}.${fmt}`,
    drawOverlay: drawMarkers,
    onClick: handleClick,
    onHover: handleHover,
  });
  map.fit();

  // Dragging the map is a deliberate look-somewhere-else, so it releases
  // follow. Wheel zoom deliberately does not. This lives here rather than in
  // wireUi() because switchMaster() replaces the canvas on every layer change.
  map.canvas.addEventListener('pointerdown', () => setFollow(false));
}

/* ------------------------------------------------------------ marker draw */

function visibleMarkers() {
  const out = [];
  for (const m of state.markers) {
    if (m.master !== state.master) continue;
    if (!state.enabled.has(m.cat)) continue;
    if (state.hideFound && isFound(m)) continue;
    out.push(m);
  }
  return out;
}

function isFound(m) {
  return state.found.has(m.id) || !!state.checked[m.id];
}

/** Grid-cluster in screen space so low zooms stay readable. */
function cluster(list, m) {
  const cell = 46;
  const grid = new Map();
  for (const mk of list) {
    const [sx, sy] = m.toScreen(mk.px, mk.py);
    const key = Math.floor(sx / cell) + ':' + Math.floor(sy / cell);
    let g = grid.get(key);
    if (!g) { g = { sx: 0, sy: 0, items: [] }; grid.set(key, g); }
    g.sx += sx; g.sy += sy; g.items.push(mk);
  }
  const out = [];
  for (const g of grid.values()) {
    const n = g.items.length;
    out.push({ sx: g.sx / n, sy: g.sy / n, items: g.items });
  }
  return out;
}

function drawMarkers(ctx, m) {
  const r = m.canvas.getBoundingClientRect();
  const list = visibleMarkers();
  const useClusters = m.scale < 0.28;
  state.clusters = useClusters ? cluster(list, m) : null;

  ctx.save();
  ctx.lineWidth = 1.5;

  if (useClusters) {
    for (const c of state.clusters) {
      if (c.sx < -40 || c.sy < -40 || c.sx > r.width + 40 || c.sy > r.height + 40) continue;
      if (c.items.length === 1) { drawOne(ctx, c.items[0], c.sx, c.sy, m); continue; }
      const foundN = c.items.filter(isFound).length;
      const rad = Math.min(14, 7 + Math.log2(c.items.length) * 2.1);
      ctx.beginPath();
      ctx.arc(c.sx, c.sy, rad, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(16,14,10,.78)';
      ctx.fill();
      ctx.strokeStyle = foundN === c.items.length ? FOUND_COLOR : '#d8b45a';
      ctx.stroke();
      ctx.fillStyle = foundN === c.items.length ? '#bfe6c4' : '#e6dfcd';
      ctx.font = '600 10px "Segoe UI", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(c.items.length), c.sx, c.sy);
    }
  } else {
    for (const mk of list) {
      const [sx, sy] = m.toScreen(mk.px, mk.py);
      if (sx < -30 || sy < -30 || sx > r.width + 30 || sy > r.height + 30) continue;
      drawOne(ctx, mk, sx, sy, m);
    }
    if (state.showLabels && m.scale > 0.85) {
      ctx.font = '11px "Segoe UI", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      // Boss markers borrow the name of the nearest landmark, so the same text
      // can land twice in one spot. Draw each name once per neighbourhood.
      const drawn = [];
      for (const mk of list) {
        if (mk.cat !== 'grace' && mk.cat !== 'boss') continue;
        const [sx, sy] = m.toScreen(mk.px, mk.py);
        if (sx < 0 || sy < 0 || sx > r.width || sy > r.height) continue;
        const label = nameOf(mk);
        if (drawn.some((d) => d.name === label &&
                       Math.abs(d.x - sx) < 90 && Math.abs(d.y - sy) < 60)) continue;
        drawn.push({ name: label, x: sx, y: sy });
        ctx.lineWidth = 3;
        ctx.strokeStyle = 'rgba(8,7,5,.9)';
        ctx.strokeText(label, sx, sy + 9);
        ctx.fillStyle = isFound(mk) ? 'rgba(160,200,165,.95)' : 'rgba(230,223,205,.95)';
        ctx.fillText(label, sx, sy + 9);
        ctx.lineWidth = 1.5;
      }
    }
  }

  drawFragmentRect(ctx, m);
  drawPlayer(ctx, m);
  ctx.restore();
}

/** A selected map fragment shows the region it reveals. */
function drawFragmentRect(ctx, m) {
  const mk = state.selected && state.byId.get(state.selected);
  if (!mk || mk.cat !== 'fragment' || !mk.rect || mk.master !== state.master) return;
  const [x0, y0] = m.toScreen(mk.rect[0], mk.rect[1]);
  const [x1, y1] = m.toScreen(mk.rect[2], mk.rect[3]);
  ctx.save();
  ctx.setLineDash([7, 5]);
  ctx.strokeStyle = isFound(mk) ? 'rgba(111,207,122,.85)' : 'rgba(197,139,234,.85)';
  ctx.lineWidth = 2;
  ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
  ctx.fillStyle = isFound(mk) ? 'rgba(111,207,122,.07)' : 'rgba(197,139,234,.09)';
  ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
  ctx.restore();
}

function drawOne(ctx, mk, sx, sy, m) {
  const cat = CATS[mk.cat] || CATS.poi;
  const found = isFound(mk);
  const sel = state.selected === mk.id;
  const hov = state.hovered === mk.id;
  const rad = (cat.r + (hov || sel ? 2.5 : 0)) * (m.scale > 1.6 ? 1.25 : 1);

  const ic = iconFor(mk);
  if (ic) {
    // Constant display size regardless of zoom, like the game's own map.
    const h = 26 * (m.scale > 1.6 ? 1.3 : 1) * (hov || sel ? 1.25 : 1);
    const w = h * (ic.meta.w / ic.meta.h);
    ctx.save();
    // A few sprites are directional (the grace rays, the summoning-pool flames)
    // and carry the heading the game draws them at.
    if (mk.angle) {
      ctx.translate(sx, sy);
      ctx.rotate(mk.angle * Math.PI / 180);
      ctx.translate(-sx, -sy);
    }
    // Sprites have no flat colour to tint, so "found" is shown by fading the
    // sprite and putting the usual tick on top.
    ctx.globalAlpha = found ? 0.4 : 1;
    ctx.drawImage(ic.img, sx - w / 2, sy - h / 2, w, h);
    ctx.restore();
    if (found) {
      ctx.beginPath();
      ctx.moveTo(sx - rad * 0.42, sy);
      ctx.lineTo(sx - rad * 0.08, sy + rad * 0.38);
      ctx.lineTo(sx + rad * 0.46, sy - rad * 0.4);
      ctx.strokeStyle = FOUND_COLOR;
      ctx.lineWidth = 2.2;
      ctx.stroke();
    }
    if (sel) {
      ctx.beginPath();
      ctx.arc(sx, sy, h * 0.62, 0, Math.PI * 2);
      ctx.strokeStyle = cat.color;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    return;
  }

  ctx.beginPath();
  ctx.arc(sx, sy, rad, 0, Math.PI * 2);
  ctx.fillStyle = found ? 'rgba(24,34,24,.9)' : 'rgba(14,12,9,.85)';
  ctx.fill();
  ctx.strokeStyle = found ? FOUND_COLOR : cat.color;
  ctx.lineWidth = sel ? 2.6 : 1.6;
  ctx.stroke();

  if (found) {
    ctx.beginPath();
    ctx.moveTo(sx - rad * 0.42, sy);
    ctx.lineTo(sx - rad * 0.08, sy + rad * 0.38);
    ctx.lineTo(sx + rad * 0.46, sy - rad * 0.4);
    ctx.strokeStyle = FOUND_COLOR;
    ctx.lineWidth = 1.9;
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.arc(sx, sy, Math.max(1.2, rad * 0.3), 0, Math.PI * 2);
    ctx.fillStyle = cat.color;
    ctx.fill();
  }
}

/**
 * The player dot.
 *
 * Prefers the live memory feed when it is running, otherwise falls back to the
 * position recorded in the last save. Live samples arrive at ~20 Hz while the
 * canvas redraws at display rate, so the rendered point is eased toward the
 * newest sample rather than snapped to it.
 */
const LIVE_STALE_MS = 5000;

/**
 * The player dot animates (pulse ring, eased motion), which means the canvas
 * has to keep redrawing. Doing that every animation frame would spin the GPU at
 * display rate for the whole session - wasteful in general, and actively rude
 * when this is running alongside the game it is tracking. ~18 fps is smooth
 * enough for a marker and costs a fraction of that. Nothing is scheduled at all
 * while the tab is in the background.
 */
const ANIM_INTERVAL_MS = 55;
let animTimer = null;

function scheduleAnimation() {
  if (animTimer !== null || document.hidden) return;
  animTimer = setTimeout(() => {
    animTimer = null;
    if (!document.hidden) map.requestDraw();
  }, ANIM_INTERVAL_MS);
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden && map) map.requestDraw();
});

function playerTarget() {
  const p = state.livePos;
  if (p && Date.now() - p.t < LIVE_STALE_MS) {
    return { px: p.px, py: p.py, master: p.master, angle: p.angle,
             live: true, roundtable: p.roundtable };
  }
  const c = state.character;
  if (c && c.mapPixel) {
    return { px: c.mapPixel[0], py: c.mapPixel[1], master: c.mapMaster,
             angle: null, live: false, roundtable: false };
  }
  return null;
}

/**
 * Follow mode. Engaged, every new position re-centres the map and a cross-map
 * move switches the layer with you. It stays engaged while the position is
 * unknown - only clicking the button again, or dragging the map, releases it -
 * so turning it on before the game is running does the right thing once the
 * reader attaches.
 */
function setFollow(on) {
  if (state.followPlayer === on) return;
  state.followPlayer = on;
  const btn = $('goto-player');
  btn.classList.toggle('active', on);
  btn.title = on ? t('zoom.following') : t('zoom.player');
  if (on) recentreOnPlayer();
}

function recentreOnPlayer() {
  if (!state.followPlayer) return;
  const p = playerTarget();
  if (!p) return;
  if (p.master && p.master !== state.master) switchMaster(p.master);
  map.centerOn(p.px, p.py, Math.max(map.scale, 1.2));
}

function drawPlayer(ctx, m) {
  const target = playerTarget();
  if (!target) { state.playerRender = null; return; }
  if (target.master !== state.master) return;

  // ease toward the newest sample (snap if it teleported, e.g. a warp)
  let r = state.playerRender;
  if (!r || Math.hypot(r.px - target.px, r.py - target.py) > 400) {
    r = { px: target.px, py: target.py, angle: target.angle };
  } else {
    const k = 0.25;
    r.px += (target.px - r.px) * k;
    r.py += (target.py - r.py) * k;
    if (target.angle != null) {
      if (r.angle == null) r.angle = target.angle;
      else {
        let d = ((target.angle - r.angle + 540) % 360) - 180;   // shortest way round
        r.angle += d * k;
      }
    }
  }
  state.playerRender = r;

  const [sx, sy] = m.toScreen(r.px, r.py);
  const pulse = 10 + Math.sin(performance.now() / 600) * 3;

  // facing cone, when the live feed gives us a heading
  if (r.angle != null) {
    const a = (r.angle - 90) * Math.PI / 180;
    const spread = 0.42;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.arc(sx, sy, 26, a - spread, a + spread);
    ctx.closePath();
    const g = ctx.createRadialGradient(sx, sy, 3, sx, sy, 26);
    g.addColorStop(0, 'rgba(255,255,255,.34)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fill();
  }

  ctx.beginPath();
  ctx.arc(sx, sy, pulse, 0, Math.PI * 2);
  ctx.strokeStyle = target.live ? 'rgba(120,220,255,.5)' : 'rgba(255,255,255,.3)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(sx, sy, 5, 0, Math.PI * 2);
  ctx.fillStyle = target.live ? '#8fe3ff' : '#fff';
  ctx.fill();
  ctx.strokeStyle = '#12181c';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Keep animating only while there is something to animate.
  const settled = Math.abs(r.px - target.px) < 0.05 && Math.abs(r.py - target.py) < 0.05;
  if (!settled || target.live) scheduleAnimation();
}

/* ---------------------------------------------------------------- picking */

function pick(sx, sy) {
  if (state.clusters) {
    for (const c of state.clusters) {
      const d = Math.hypot(c.sx - sx, c.sy - sy);
      if (d < 19) return { cluster: c };
    }
    return null;
  }
  let best = null, bestD = 15;
  for (const mk of visibleMarkers()) {
    const [x, y] = map.toScreen(mk.px, mk.py);
    const d = Math.hypot(x - sx, y - sy);
    if (d < bestD) { bestD = d; best = mk; }
  }
  return best ? { marker: best } : null;
}

function handleHover(sx, sy) {
  const hit = pick(sx, sy);
  const tip = $('tooltip');
  const id = hit && hit.marker ? hit.marker.id : null;
  if (id !== state.hovered) { state.hovered = id; map.requestDraw(); }

  if (hit && hit.marker) {
    const m = hit.marker;
    tip.innerHTML = `<div>${escapeHtml(nameOf(m))}</div>` +
      `<div class="tt-cat">${catLabel(m.cat)}${isFound(m) ? ' · ' + t('tip.found') : ''}</div>`;
    const [x, y] = map.toScreen(m.px, m.py);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
    tip.classList.remove('hidden');
  } else if (hit && hit.cluster) {
    const n = hit.cluster.items.length;
    tip.innerHTML = `<div>${n} ${I18n.plural('tip.markers', n)}</div>` +
      `<div class="tt-cat">${t('tip.clickZoom')}</div>`;
    tip.style.left = hit.cluster.sx + 'px';
    tip.style.top = hit.cluster.sy + 'px';
    tip.classList.remove('hidden');
  } else {
    tip.classList.add('hidden');
  }
}

function handleClick(sx, sy) {
  const hit = pick(sx, sy);
  if (!hit) { closePopup(); return; }
  if (hit.cluster) {
    const [mx, my] = map.toMaster(hit.cluster.sx, hit.cluster.sy);
    map.flyTo(mx, my, map.scale * 2.5);
    return;
  }
  showPopup(hit.marker);
}

/* ----------------------------------------------------------------- popup */

/**
 * How high up is it?
 *
 * The extractors carry the world Y through the same translation chain as the
 * horizontal axes (see LegacyConv.convert in tools/build_markers.py), so these
 * are comparable across maps: the Forge of the Giants reads ~1970, the Siofra
 * River well bottom ~-480. A world unit is about a metre.
 *
 * Map fragments have no height - they are the centre of the region a fragment
 * reveals, not a thing standing anywhere - so their row is simply omitted.
 */
function heightBlock(m) {
  if (typeof m.h !== 'number') return '';
  return '<div class="detail">' +
    `<span class="k">${escapeHtml(t('popup.height'))}</span>` +
    `<span class="v">${m.h} ${escapeHtml(t('unit.m'))}</span></div>`;
}

function showPopup(m) {
  state.selected = m.id;
  const el = $('popup');
  const found = isFound(m);
  const auto = state.found.has(m.id);
  el.innerHTML = `
    <button class="close" title="${escapeHtml(t('popup.close'))}">×</button>
    <h3>${escapeHtml(nameOf(m))}</h3>
    <div class="meta">${catLabel(m.cat)}${m.map ? ' · ' + m.map : ''}${m.flag ? ' · ' + m.flag : ''}</div>
    <div class="found-state ${found ? 'found-yes' : ''}">
      ${found ? (auto ? t('popup.foundSave') : t('popup.foundManual')) : t('popup.notFound')}
    </div>
    ${heightBlock(m)}
    ${auto ? '' : `<button class="toggle">${found ? t('popup.unmark') : t('popup.mark')}</button>`}
  `;
  const [x, y] = map.toScreen(m.px, m.py);
  el.style.left = x + 'px';
  el.style.top = y + 'px';
  el.classList.remove('hidden');
  el.querySelector('.close').onclick = closePopup;
  // NOT `const t` - that would shadow the translate helper used in the template
  // above and put it in the temporal dead zone for the whole function.
  const btn = el.querySelector('.toggle');
  if (btn) btn.onclick = () => toggleCheck(m.id, !found);
  map.requestDraw();
}

function closePopup() {
  state.selected = null;
  $('popup').classList.add('hidden');
  if (map) map.requestDraw();
}

async function toggleCheck(id, on) {
  if (on) state.checked[id] = true; else delete state.checked[id];
  refreshCounts();
  map.requestDraw();
  const m = state.byId.get(id);
  if (m) showPopup(m);
  try {
    await fetch('api/check', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, on }),
    });
  } catch { /* offline; local state still applies */ }
}

/* ------------------------------------------------------------------- ui */

function buildLayerButtons() {
  const wrap = $('layer-buttons');
  wrap.innerHTML = '';
  const order = ['M00', 'M01', 'M10', 'M11'];
  for (const id of order) {
    const info = masterInfo(id);
    const b = document.createElement('button');
    b.className = 'layer-btn' + (id === state.master ? ' active' : '');
    b.textContent = t('master.' + id);
    b.disabled = !info;
    b.onclick = () => switchMaster(id);
    wrap.appendChild(b);
  }
}

function switchMaster(id) {
  if (!masterInfo(id) || id === state.master) return;
  state.master = id;
  closePopup();
  buildLayerButtons();
  initMap(id);
  refreshCounts();
}

function buildCategories() {
  const wrap = $('category-list');
  wrap.innerHTML = '';
  for (const key of Object.keys(CATS)) {
    const row = document.createElement('div');
    row.className = 'cat' + (state.enabled.has(key) ? '' : ' off');
    row.dataset.cat = key;
    // 50-odd item categories is too many to tell apart by colour alone, so a
    // category that has an icon shows it in place of the swatch.
    const icon = CATS[key].icon;
    // Not loading="lazy": these are ~50 small PNGs off the local server, and a
    // lazy swatch stays blank whenever the sidebar is scrolled or collapsed.
    const swatch = icon
      ? `<img class="swatch icon" src="icons/categories/${icon}" alt="">`
      : `<span class="swatch" style="background:${CATS[key].color}"></span>`;
    row.innerHTML = `
      ${swatch}
      <span class="label">${escapeHtml(catLabel(key))}<span class="minibar"><i style="width:0%"></i></span></span>
      <span class="count">0/0</span>`;
    row.onclick = () => {
      if (state.enabled.has(key)) state.enabled.delete(key); else state.enabled.add(key);
      row.classList.toggle('off', !state.enabled.has(key));
      map.requestDraw();
    };
    wrap.appendChild(row);
  }
}

/**
 * The save picker: one dropdown for the save extension (vanilla .sl2, Reforged
 * .err, whatever else is installed) and one for the file itself, labelled by
 * the characters inside it rather than the Steam account id.
 */
function buildSavePicker() {
  const extension = $('save-extension');
  const file = $('save-file');
  const extensions = [...new Set(state.saves.map((save) => save.extension))];
  const selected = state.saves.find((save) => save.path === state.savePath);
  extension.innerHTML = extensions.map((value) =>
    `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
  extension.value = (selected && selected.extension) || extensions[0] || '';

  const renderFiles = () => {
    const matches = state.saves.filter((save) => save.extension === extension.value);
    file.innerHTML = matches.map((save) => {
      const chars = save.characters || [];
      const label = chars.length
        ? chars.map((c) => `${c.name} · ${t('char.level')} ${c.level}`).join(' / ')
        : `${t('save.account')} ${save.account}`;
      return `<option value="${escapeHtml(save.path)}" title="${escapeHtml(save.path)}">${escapeHtml(label)}</option>`;
    }).join('');
    const current = matches.find((save) => save.path === state.savePath);
    file.value = (current && current.path) || (matches[0] && matches[0].path) || '';
    file.disabled = matches.length === 0;
  };

  extension.onchange = renderFiles;
  file.onchange = async () => {
    if (!file.value || file.value === state.savePath) return;
    extension.disabled = true;
    file.disabled = true;
    try {
      const response = await fetch('api/saves', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: file.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || t('save.switchFailed'));
      state.savePath = result.current;
    } catch (error) {
      toast(t('save.switchFailed'), error.message);
    } finally {
      extension.disabled = false;
      renderFiles();          // also re-enables the file select
    }
  };
  renderFiles();
}

function refreshCounts() {
  let total = 0, found = 0;
  for (const key of Object.keys(CATS)) {
    const all = state.markers.filter((m) => m.cat === key && m.master === state.master);
    const f = all.filter(isFound).length;
    total += all.length; found += f;
    const row = document.querySelector(`.cat[data-cat="${key}"]`);
    if (!row) continue;
    row.querySelector('.count').textContent = `${f}/${all.length}`;
    row.querySelector('.minibar i').style.width = all.length ? (f / all.length * 100) + '%' : '0%';
    row.style.display = all.length ? '' : 'none';
  }
  $('progress-label').textContent = `${found} / ${total}`;
  $('progress-fill').style.width = total ? (found / total * 100) + '%' : '0%';
}

function wireUi() {
  // Collapsible panels: every [data-collapse] header folds its own section.
  document.querySelectorAll('[data-collapse]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const section = btn.closest('.panel');
      if (section) section.classList.toggle('collapsed');
    });
  });

  // ...and the whole sidebar, so the map can have the full window.
  const app = $('app');
  $('sb-collapse').onclick = () => app.classList.add('sb-collapsed');
  $('sb-expand').onclick = () => app.classList.remove('sb-collapsed');

  $('zoom-in').onclick = () => map.zoomBy(1.6);
  $('zoom-out').onclick = () => map.zoomBy(1 / 1.6);
  $('zoom-fit').onclick = () => map.fit();
  $('goto-player').onclick = () => {
    if (state.followPlayer) { setFollow(false); return; }
    if (!playerTarget()) toast(t('zoom.noPlayer'), t('zoom.noPlayerSub'));
    setFollow(true);      // engage regardless: it takes effect once a fix arrives
  };

  $('hide-found').onchange = (e) => { state.hideFound = e.target.checked; map.requestDraw(); };
  $('show-labels').onchange = (e) => { state.showLabels = e.target.checked; map.requestDraw(); };
  const gi = $('show-icons');
  if (gi) {
    gi.checked = state.showIcons;
    gi.onchange = (e) => { state.showIcons = e.target.checked; map.requestDraw(); };
  }

  $('toggle-all').onclick = () => {
    if (state.enabled.size) state.enabled.clear();
    else Object.keys(CATS).forEach((k) => state.enabled.add(k));   // all, incl. misc
    document.querySelectorAll('.cat').forEach((r) =>
      r.classList.toggle('off', !state.enabled.has(r.dataset.cat)));
    $('toggle-all').textContent = state.enabled.size ? t('panel.selectNone') : t('panel.selectAll');
    map.requestDraw();
  };

  const search = $('search');
  const results = $('search-results');
  search.oninput = () => {
    const q = search.value.trim().toLowerCase();
    if (q.length < 2) { results.classList.remove('open'); return; }
    // Search every locale's name, so an English query still finds a marker
    // while the UI is in Russian (and vice versa).
    const hits = state.markers
      .filter((m) => {
        const names = m.names ? Object.values(m.names) : [m.name || ''];
        return names.some((n) => n && n.toLowerCase().includes(q));
      })
      .slice(0, 40);
    results.innerHTML = hits.length
      ? hits.map((m) => `<div class="sr-item" data-id="${m.id}">
           <span class="swatch" style="width:9px;height:9px;border-radius:50%;background:${(CATS[m.cat]||CATS.poi).color}"></span>
           <span>${escapeHtml(nameOf(m))}</span>
           <span class="sr-cat">${isFound(m) ? '✓ ' : ''}${m.master || ''}</span></div>`).join('')
      : `<div class="sr-item dim">${escapeHtml(t('search.none'))}</div>`;
    results.classList.add('open');
    results.querySelectorAll('.sr-item[data-id]').forEach((el) => {
      el.onclick = () => {
        const m = state.byId.get(el.dataset.id);
        if (!m) return;
        if (m.master !== state.master) switchMaster(m.master);
        results.classList.remove('open');
        search.value = '';
        map.flyTo(m.px, m.py, Math.max(map.scale, 1.4));
        setTimeout(() => showPopup(m), 430);
      };
    });
  };
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrap')) results.classList.remove('open');
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closePopup(); results.classList.remove('open'); }
    if (e.key === '/' && document.activeElement !== search) { e.preventDefault(); search.focus(); }
  });

  setTimeout(() => $('hint').classList.add('gone'), 6000);
}

/* --------------------------------------------------------------- live */

function connect() {
  const es = new EventSource('api/events');
  es.addEventListener('open', () => setLive(true));
  es.addEventListener('error', () => setLive(false));
  es.addEventListener('state', (ev) => {
    try { applyState(JSON.parse(ev.data)); setLive(true); }
    catch (e) { console.error('bad state frame', e); }
  });
  // Real-time position, only present when the server runs with --live-memory.
  es.addEventListener('pos', (ev) => {
    try {
      const p = JSON.parse(ev.data);
      state.livePos = p;
      recentreOnPlayer();
      // The server matches the running character to a save slot by position.
      // Swap the displayed progress over when that answer changes.
      const active = state.characters.find((character) => character.slot === p.slot);
      if (active && active !== state.character) {
        state.character = active;
        state.found = new Set(active.found || []);
        renderCharacter(active);
        refreshCounts();
      }
      if (map) map.requestDraw();
    } catch { /* ignore a malformed frame */ }
  });
  es.addEventListener('live', (ev) => {
    try {
      const st = JSON.parse(ev.data);
      state.liveStatus = st.status;
      if (st.status !== 'live') state.livePos = null;
      if (state.character) renderCharacter(state.character);
    } catch { /* ignore */ }
  });
  es.addEventListener('checked', (ev) => {
    const { id, on } = JSON.parse(ev.data);
    if (on) state.checked[id] = true; else delete state.checked[id];
    refreshCounts(); map.requestDraw();
  });
}

function setLive(on) {
  $('live').classList.toggle('on', on);
  $('live').classList.toggle('off', !on);
  $('live-text').textContent = on ? t('live.on') : t('live.off');
}

function applyState(s) {
  state.checked = s.checked || {};
  // Every snapshot carries the live reader's state. Without this the badge
  // stayed blank on a fresh page load until the status happened to change.
  if (s.live) state.liveStatus = s.live.status;
  state.savePath = s.savePath || state.savePath;

  // The server projects each save position with the same affine as the markers.
  // Every slot is converted, not just the displayed one, because a `pos` frame
  // can switch to any of them without another snapshot arriving first.
  state.characters = (s.characters || []).map((c) => {
    const mp = c.mapPixel;
    return { ...c, mapPixel: mp ? [mp.px, mp.py] : null, mapMaster: mp ? mp.master : null };
  });

  // Show the slot the live reader matched to the running game; without a live
  // feed there is nothing to match against, so fall back to the first slot.
  const c = state.characters.find((x) => x.slot === s.activeSlot) || state.characters[0];
  if (!c) { $('char-name').textContent = t('app.noCharacter'); return; }

  state.found = new Set(c.found || []);
  state.character = c;

  renderCharacter(c);
  refreshCounts();
  if (map) map.requestDraw();
  recentreOnPlayer();

  for (const n of (s.newlyFound || [])) {
    for (const id of n.ids.slice(0, 4)) {
      const m = state.byId.get(id);
      if (m) toast(nameOf(m), catLabel(m.cat));
    }
    if (n.ids.length > 4) toast(`+${n.ids.length - 4} ${t('toast.more')}`, t('toast.discovered'));
  }
}

/** One line describing the optional live-memory feed, or nothing when it is off. */
function liveBadge() {
  const st = state.liveStatus;
  if (!st || st === 'off') return '';
  const map = {
    live:    ['#8fe3ff', 'live.realtime'],
    waiting: ['#9a917c', 'live.waiting'],
    starting:['#9a917c', 'live.waiting'],
    error:   ['#e0a35a', 'live.denied'],
    stopped: ['#9a917c', 'live.waiting'],
  };
  const [color, key] = map[st] || ['#9a917c', 'live.waiting'];
  return `<br><span style="color:${color}">&#9679; ${escapeHtml(t(key))}</span>`;
}

/** Sidebar character panel. Split out so a language switch can re-render it. */
function renderCharacter(c) {
  $('char-name').textContent = c.name || '—';
  const secs = c.secondsPlayed || 0;
  const hrs = Math.floor(secs / 3600);
  const mins = Math.floor((secs % 3600) / 60);
  $('char-meta').textContent =
    `${t('char.level')} ${c.level} · ${hrs}${t('char.hoursShort')} ` +
    `${String(mins).padStart(2, '0')}${t('char.minutesShort')}` +
    (c.deaths != null ? ` · ${c.deaths} ${I18n.plural('char.deaths', c.deaths)}` : '');

  // Stat abbreviations are the same glyphs the game uses in both languages.
  const st = c.stats;
  $('char-stats').innerHTML = st ? [
    ['VIG', st.vigor], ['MND', st.mind], ['END', st.endurance], ['STR', st.strength],
    ['DEX', st.dexterity], ['INT', st.intelligence], ['FTH', st.faith], ['ARC', st.arcane],
  ].map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('') : '';

  let where = c.position
    ? `${escapeHtml(t('char.lastSave'))}: <b>${c.position.mapId}</b><br>` +
      `${st ? st.runes.toLocaleString(I18n.lang === 'ru' ? 'ru-RU' : 'en-US') : '—'} ${escapeHtml(t('char.runes'))}`
    : (c.error ? `<span style="color:#e05a5a">${escapeHtml(t('err.saveRead'))}: ${escapeHtml(c.error)}</span>` : '');
  where += liveBadge();
  $('char-where').innerHTML = where;

  if (!c.ok && c.error) {
    $('foot').textContent = `${t('err.parse')}: ${c.error}`;
  } else {
    $('foot').textContent =
      `${state.markers.length} ${t('foot.markers')} · ${t('foot.flagsAt')} 0x${(c.flagOffset || 0).toString(16)}`;
  }
}

function toast(title, sub) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `<div>${escapeHtml(title)}</div><div class="t-cat">${escapeHtml(sub || '')}</div>`;
  $('toasts').appendChild(el);
  setTimeout(() => { el.style.transition = 'opacity .5s'; el.style.opacity = '0'; }, 4200);
  setTimeout(() => el.remove(), 4800);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

boot();
