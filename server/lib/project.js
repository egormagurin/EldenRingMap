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

/**
 * Sort key that puts a block's real anchor row first.
 *
 * A block usually gets one row per overworld cell it straddles, all describing
 * the same world point, so the choice is arbitrary. Not for Farum Azula, the
 * Finger Birthing Grounds and the Haligtree, whose rows disagree by hundreds of
 * pixels - see LegacyConv in tools/build_markers.py.
 */
function anchorRank(r) {
  return [(r.dst[0] === 60 || r.dst[0] === 61) ? 0 : 1,
          r.base ? 0 : 1,
          (r.srcPos[0] || r.srcPos[2]) ? 0 : 1,
          (r.dstPos[0] || r.dstPos[2]) ? 0 : 1];
}

class Projector {
  constructor(convDoc) {
    this.byBlock = new Map();
    for (const r of (convDoc && convDoc.rows) || []) {
      const key = r.src.join(',');
      if (!this.byBlock.has(key)) this.byBlock.set(key, []);
      this.byBlock.get(key).push(r);
    }
    for (const rows of this.byBlock.values()) {
      rows.sort((a, b) => {                            // Array#sort is stable, so
        const ka = anchorRank(a), kb = anchorRank(b);  // equal rows keep param order
        for (let i = 0; i < ka.length; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
        return 0;
      });
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
        h: y,
        area,
      };
    }
    if (depth > 4) return null;
    const rows = this._rows(area, block, mapno);
    if (!rows || !rows.length) return null;
    const best = rows[0];                    // anchorRank order, so one row per block
    return this._resolve(
      best.dst[0], best.dst[1], best.dst[2],
      x - best.srcPos[0] + best.dstPos[0],
      y - best.srcPos[1] + best.dstPos[1],
      z - best.srcPos[2] + best.dstPos[2],
      depth + 1);
  }

  /**
   * position from the save -> { px, py, master, h } or null.
   *
   * `h` is the world height, translated through the same chain as the
   * horizontal axes, so it is directly comparable with the `h` on markers
   * (see LegacyConv.convert in tools/build_markers.py, which mirrors this).
   */
  project(position) {
    if (!position || !position.mapBytes) return null;
    const b = position.mapBytes;          // [DD, CC, BB, AA]
    const area = b[3], block = b[2], mapno = b[1];
    const r = this._resolve(area, block, mapno, position.x, position.y, position.z);
    if (!r) return null;
    const master = r.area === 61 ? 'M10'
      : (this.underground.has(`${area},${block}`) ? 'M01' : 'M00');
    return { px: Math.round(r.px * 10) / 10, py: Math.round(r.py * 10) / 10,
             h: Math.round(r.h), master };
  }
}

module.exports = { Projector, TILE_WORLD, OFFSET_X, OFFSET_Y };
