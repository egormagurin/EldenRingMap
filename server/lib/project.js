'use strict';
/**
 * World position -> master-image pixel.
 *
 * Mirrors tools/build_markers.py exactly, so the live player dot lands in the
 * same space as the markers. Kept server-side rather than in the browser so
 * there is one implementation of the affine, not two.
 *
 *   S      = 256                     world units per overworld grid cell
 *   worldX = gridX*S + S/2 + posX    a cell's centre is its local origin
 *   worldZ = gridZ*S + S/2 + posZ
 *   px     = worldX - 7168
 *   py     = 16640 - worldZ
 *
 * Legacy dungeons carry their own local frame and are translated onto the
 * overworld through WorldMapLegacyConvParam. Some rows hop dungeon -> dungeon,
 * so resolution follows chains.
 */
const TILE_WORLD = 256;
const OFFSET_X = -7168;
const OFFSET_Y = 16640;

class Projector {
  constructor(convDoc) {
    this.byBlock = new Map();
    for (const r of (convDoc && convDoc.rows) || []) {
      const key = r.src.join(',');
      if (!this.byBlock.has(key)) this.byBlock.set(key, []);
      this.byBlock.get(key).push(r);
    }
    this.underground = new Set(
      ((convDoc && convDoc.undergroundBlocks) || []).map((b) => b.join(',')));
  }

  _rows(area, block, mapno) {
    return this.byBlock.get(`${area},${block},${mapno}`)
        || this.byBlock.get(`${area},${block},0`);
  }

  _resolve(area, block, mapno, x, y, z, depth = 0) {
    if (area === 60 || area === 61) {
      return {
        px: block * TILE_WORLD + TILE_WORLD / 2 + x + OFFSET_X,
        py: OFFSET_Y - (mapno * TILE_WORLD + TILE_WORLD / 2 + z),
        area,
      };
    }
    if (depth > 4) return null;
    const rows = this._rows(area, block, mapno);
    if (!rows || !rows.length) return null;
    const direct = rows.filter((r) => r.dst[0] === 60 || r.dst[0] === 61);
    const pool = direct.length ? direct : rows;
    let best = pool[0];
    let bestD = Infinity;
    for (const r of pool) {
      const d = (r.srcPos[0] - x) ** 2 + (r.srcPos[2] - z) ** 2;
      if (d < bestD) { bestD = d; best = r; }
    }
    return this._resolve(
      best.dst[0], best.dst[1], best.dst[2],
      x - best.srcPos[0] + best.dstPos[0],
      y - best.srcPos[1] + best.dstPos[1],
      z - best.srcPos[2] + best.dstPos[2],
      depth + 1);
  }

  /** position from the save -> { px, py, master } or null. */
  project(position) {
    if (!position || !position.mapBytes) return null;
    const b = position.mapBytes;          // [DD, CC, BB, AA]
    const area = b[3], block = b[2], mapno = b[1];
    const r = this._resolve(area, block, mapno, position.x, position.y, position.z);
    if (!r) return null;
    const master = r.area === 61 ? 'M10'
      : (this.underground.has(`${area},${block}`) ? 'M01' : 'M00');
    return { px: Math.round(r.px * 10) / 10, py: Math.round(r.py * 10) / 10, master };
  }
}

module.exports = { Projector, TILE_WORLD, OFFSET_X, OFFSET_Y };
