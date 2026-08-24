'use strict';
/**
 * Minimal canvas tile-map engine.
 *
 * Coordinates: everything public is in MASTER PIXELS - the 10496x10496 space the
 * tiles were stitched in, which is also the space the marker affine produces. The
 * engine converts to screen space only at draw time.
 *
 * Drawing markers on a canvas rather than as DOM nodes is what keeps a few
 * thousand of them smooth; hit-testing is done against the same projection.
 */

class TileMap {
  constructor(canvas, opts) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', { alpha: false });

    this.tileSize = opts.tileSize || 256;
    this.width = opts.width || 10496;
    this.height = opts.height || 10496;
    this.nativeZoom = opts.nativeZoom ?? 6;
    this.tileUrl = opts.tileUrl;              // (z, x, y) -> url
    this.tileIndex = opts.tileIndex || null;  // {z: Set("x,y")} - avoids 404 storms
    this.background = opts.background || '#070705';

    this.scale = 1;                           // screen px per master px
    this.minScale = 0.02;
    this.maxScale = 4;
    this.cx = this.width / 2;                 // camera centre, master px
    this.cy = this.height / 2;

    this.cache = new Map();                   // url -> Image | 'pending' | 'error'
    this.cacheOrder = [];
    this.maxCache = 900;

    this.drawOverlay = opts.drawOverlay || (() => {});
    this.onClick = opts.onClick || (() => {});
    this.onHover = opts.onHover || (() => {});

    this._raf = null;
    this._bind();
    this.resize();
  }

  /* ------------------------------------------------------------ transforms */

  toScreen(px, py) {
    const r = this.canvas.getBoundingClientRect();
    return [(px - this.cx) * this.scale + r.width / 2,
            (py - this.cy) * this.scale + r.height / 2];
  }

  toMaster(sx, sy) {
    const r = this.canvas.getBoundingClientRect();
    return [(sx - r.width / 2) / this.scale + this.cx,
            (sy - r.height / 2) / this.scale + this.cy];
  }

  /* ------------------------------------------------------------- viewport */

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.max(1, Math.round(r.width * dpr));
    this.canvas.height = Math.max(1, Math.round(r.height * dpr));
    this.dpr = dpr;
    this.fitScale = Math.min(r.width / this.width, r.height / this.height);
    this.minScale = this.fitScale * 0.85;
    this.requestDraw();
  }

  fit() {
    const r = this.canvas.getBoundingClientRect();
    this.scale = Math.min(r.width / this.width, r.height / this.height) * 0.98;
    this.cx = this.width / 2;
    this.cy = this.height / 2;
    this.requestDraw();
  }

  zoomBy(factor, anchorX, anchorY) {
    const r = this.canvas.getBoundingClientRect();
    const ax = anchorX ?? r.width / 2;
    const ay = anchorY ?? r.height / 2;
    const [mx, my] = this.toMaster(ax, ay);
    const next = Math.max(this.minScale, Math.min(this.maxScale, this.scale * factor));
    if (next === this.scale) return;
    this.scale = next;
    // keep the anchored master point under the cursor
    this.cx = mx - (ax - r.width / 2) / this.scale;
    this.cy = my - (ay - r.height / 2) / this.scale;
    this.clamp();
    this.requestDraw();
  }

  centerOn(px, py, scale) {
    this.cx = px; this.cy = py;
    if (scale) this.scale = Math.max(this.minScale, Math.min(this.maxScale, scale));
    this.clamp();
    this.requestDraw();
  }

  /** Ease the camera to a point; used by search results. */
  flyTo(px, py, scale, ms = 420) {
    const t0 = performance.now();
    const sx = this.cx, sy = this.cy, ss = this.scale;
    const ts = scale ? Math.max(this.minScale, Math.min(this.maxScale, scale)) : ss;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / ms);
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      this.cx = sx + (px - sx) * e;
      this.cy = sy + (py - sy) * e;
      this.scale = ss + (ts - ss) * e;
      this.clamp();
      this.draw();
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  clamp() {
    const r = this.canvas.getBoundingClientRect();
    const halfW = r.width / 2 / this.scale;
    const halfH = r.height / 2 / this.scale;
    const padX = Math.max(0, this.width * 0.15);
    const padY = Math.max(0, this.height * 0.15);
    this.cx = Math.max(-padX + halfW * 0, Math.min(this.width + padX, this.cx));
    this.cy = Math.max(-padY + halfH * 0, Math.min(this.height + padY, this.cy));
  }

  /* ----------------------------------------------------------------- tiles */

  tileZoom() {
    // one tile pixel per screen pixel is the ideal; bias up so it stays crisp
    const z = Math.ceil(Math.log2(this.scale) + this.nativeZoom);
    return Math.max(0, Math.min(this.nativeZoom, z));
  }

  getTile(url) {
    const hit = this.cache.get(url);
    if (hit) return hit === 'pending' || hit === 'error' ? null : hit;
    const img = new Image();
    img.decoding = 'async';
    this.cache.set(url, 'pending');
    this.cacheOrder.push(url);
    if (this.cacheOrder.length > this.maxCache) {
      const drop = this.cacheOrder.shift();
      if (drop !== url) this.cache.delete(drop);
    }
    img.onload = () => { this.cache.set(url, img); this.requestDraw(); };
    img.onerror = () => { this.cache.set(url, 'error'); };
    img.src = url;
    return null;
  }

  hasTile(z, x, y) {
    if (!this.tileIndex) return true;
    const s = this.tileIndex[z];
    return !s || s.has(x + ',' + y);
  }

  /* ------------------------------------------------------------------ draw */

  requestDraw() {
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => { this._raf = null; this.draw(); });
  }

  draw() {
    const ctx = this.ctx;
    const r = this.canvas.getBoundingClientRect();
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.fillStyle = this.background;
    ctx.fillRect(0, 0, r.width, r.height);

    const z = this.tileZoom();
    const tilesAcross = Math.pow(2, this.nativeZoom - z);      // master px per tile px
    const tileMaster = this.tileSize * tilesAcross;            // master px per tile
    const drawn = this.tileSize * tilesAcross * this.scale;    // screen px per tile

    const [x0, y0] = this.toMaster(0, 0);
    const [x1, y1] = this.toMaster(r.width, r.height);
    const cols = Math.ceil(this.width / tileMaster);
    const rows = Math.ceil(this.height / tileMaster);
    const cMin = Math.max(0, Math.floor(x0 / tileMaster));
    const cMax = Math.min(cols - 1, Math.floor(x1 / tileMaster));
    const rMin = Math.max(0, Math.floor(y0 / tileMaster));
    const rMax = Math.min(rows - 1, Math.floor(y1 / tileMaster));

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';

    for (let tx = cMin; tx <= cMax; tx++) {
      for (let ty = rMin; ty <= rMax; ty++) {
        if (!this.hasTile(z, tx, ty)) continue;
        const img = this.getTile(this.tileUrl(z, tx, ty));
        const [sx, sy] = this.toScreen(tx * tileMaster, ty * tileMaster);
        if (img) {
          // +1 hides hairline seams from fractional scaling
          ctx.drawImage(img, sx, sy, drawn + 1, drawn + 1);
        } else if (z > 0) {
          this._drawFallback(ctx, z, tx, ty, sx, sy, drawn);
        }
      }
    }

    this.drawOverlay(ctx, this);
  }

  /** While a tile loads, upscale its parent so panning never flashes empty. */
  _drawFallback(ctx, z, tx, ty, sx, sy, drawn) {
    for (let up = 1; up <= 3 && z - up >= 0; up++) {
      const pz = z - up, f = Math.pow(2, up);
      const px = Math.floor(tx / f), py = Math.floor(ty / f);
      if (!this.hasTile(pz, px, py)) continue;
      const img = this.cache.get(this.tileUrl(pz, px, py));
      if (!img || img === 'pending' || img === 'error') continue;
      const sub = this.tileSize / f;
      ctx.drawImage(img, (tx % f) * sub, (ty % f) * sub, sub, sub,
                    sx, sy, drawn + 1, drawn + 1);
      return;
    }
  }

  /* ------------------------------------------------------------- input */

  _bind() {
    const c = this.canvas;
    let dragging = false, lastX = 0, lastY = 0, moved = 0;

    c.addEventListener('pointerdown', (e) => {
      dragging = true; moved = 0;
      lastX = e.clientX; lastY = e.clientY;
      c.setPointerCapture(e.pointerId);
      c.classList.add('dragging');
    });

    c.addEventListener('pointermove', (e) => {
      const r = c.getBoundingClientRect();
      if (dragging) {
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        moved += Math.abs(dx) + Math.abs(dy);
        this.cx -= dx / this.scale;
        this.cy -= dy / this.scale;
        lastX = e.clientX; lastY = e.clientY;
        this.clamp();
        this.requestDraw();
      } else {
        this.onHover(e.clientX - r.left, e.clientY - r.top, e);
      }
    });

    const end = (e) => {
      if (!dragging) return;
      dragging = false;
      c.classList.remove('dragging');
      const r = c.getBoundingClientRect();
      if (moved < 5) this.onClick(e.clientX - r.left, e.clientY - r.top, e);
    };
    c.addEventListener('pointerup', end);
    c.addEventListener('pointercancel', () => { dragging = false; c.classList.remove('dragging'); });

    c.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = c.getBoundingClientRect();
      const f = Math.pow(1.0015, -e.deltaY);
      this.zoomBy(f, e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });

    c.addEventListener('dblclick', (e) => {
      const r = c.getBoundingClientRect();
      this.zoomBy(2, e.clientX - r.left, e.clientY - r.top);
    });

    window.addEventListener('resize', () => this.resize());
  }
}

window.TileMap = TileMap;
