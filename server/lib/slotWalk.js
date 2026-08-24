'use strict';
/**
 * Walk a decoded save slot to the things we care about.
 *
 * The slot is a sequentially-serialised struct with several variable-length
 * members (the gaitem map, the projectile list, the unlocked-region list, the
 * menu blob, the tutorial list). Nothing before the event-flag bitfield sits at
 * a fixed offset - we measured the bitfield start move by 2,216 bytes between
 * two saves minutes apart - so every field has to be walked in order.
 *
 * Ported from the verified Python reference in tools/er_save.py, which is in
 * turn derived from ClayAmore/ER-Save-Lib `src/save/user_data_x.rs`. Several
 * steps assert values the format guarantees (a 'FACE' magic, booleans that must
 * be 0/1, a 0/8 enum, and a zero terminator immediately after the bitfield), so
 * a mis-step fails loudly instead of returning plausible garbage.
 */

const EF_LEN = 0x1bf99f;          // event-flag bitfield: 1,833,375 bytes
const FLAG_DIVISOR = 1000;        // flags per block
const BLOCK_SIZE = 125;           // bytes per block (1000 bits / 8)

class WalkError extends Error {}

function walkSlot(pay) {
  const u32 = (o) => pay.readUInt32LE(o);
  const version = u32(0);
  let p = 0x20;                   // u32 version, 4B map id, 0x18 unk

  // Gaitem map: 0x1400 entries, but each entry's size depends on its handle.
  const n = version > 81 ? 0x1400 : 0x13fe;
  for (let i = 0; i < n; i++) {
    const handle = u32(p);
    p += 8;                       // gaitem handle + item id
    if (handle !== 0) {
      // `>>> 0` matters: JS bitwise ops yield a SIGNED int32, so a bare
      // `handle & 0xf0000000` can never compare equal to 0x80000000.
      const top = (handle & 0xf0000000) >>> 0;
      if (top === 0x80000000) p += 13;        // weapon: unk, unk, aow handle, pad
      else if (top === 0x90000000) p += 8;    // armour: unk, unk
    }
  }

  const playerGameData = p;
  p += 0x1b0;                     // PlayerGameData
  p += 0xd * 0x10;                // SPEffect[13]
  p += 0x58;                      // EquippedItemsEquipIndex
  p += 0x1c;                      // ActiveWeaponSlots / ArmStyle
  p += 0x58;                      // EquippedItemsItemId
  p += 0x58;                      // EquippedItemsGaitemHandle
  p += 4 + 0xa80 * 12 + 4 + 0x180 * 12 + 8;   // InventoryHeld
  p += 14 * 8 + 4;                // EquippedSpells
  p += 0xa * 8 + 4 + 6 * 8 + 8;   // EquippedItems
  p += 6 * 4;                     // EquippedGestures
  p += 4 + u32(p) * 8;            // AcquiredProjectiles (variable)
  p += 0x27 * 4;                  // EquippedArmamentsAndItems
  p += 0xc;                       // EquippedPhysics

  const faceMagic = pay.toString('latin1', p + 4, p + 8);
  if (faceMagic !== 'FACE' && faceMagic !== '\0\0\0\0') {
    throw new WalkError(`FaceData magic mismatch at 0x${p.toString(16)} (${JSON.stringify(faceMagic)})`);
  }
  p += 0x12f;                     // FaceData

  p += 4 + 0x780 * 12 + 4 + 0x80 * 12 + 8;    // InventoryStorageBox
  p += 0x40 * 4;                  // Gestures
  const regionCount = u32(p);
  p += 4 + regionCount * 4;       // Regions (variable)
  p += 0x28;                      // RideGameData
  if (pay[p] > 1) throw new WalkError(`control byte at 0x${p.toString(16)} = ${pay[p]}`);
  p += 1;
  p += 0x44;                      // BloodStain
  p += 8;                         // two unknown u32
  p += 8 + u32(p + 4);            // MenuProfileSaveLoad (variable)
  p += 0x34;                      // TrophyEquipData
  p += 8 + 7000 * 0x10;           // GaitemGameData

  const tSize = u32(p + 4);
  const tCount = u32(p + 8);
  p += 8 + (tCount === 0 ? 4 : 4 + Math.floor((tSize - 4) / 4) * 4);   // TutorialData

  p += 3;                         // gameman 0x8c / 0x8d / 0x8e
  const deaths = u32(p); p += 4;  // total_deaths_count
  const characterType = pay.readInt32LE(p); p += 4;
  p += 1;                         // in_online_session_flag
  const typeOnline = u32(p);
  if (typeOnline !== 0 && typeOnline !== 8) {
    throw new WalkError(`character_type_online = ${typeOnline} (expected 0 or 8)`);
  }
  p += 4;
  const lastRestedGrace = u32(p); p += 4;
  p += 1;                         // not_alone_flag
  p += 4;                         // in_game_countdown_timer
  p += 4;                         // unk gamedataman

  if (p + EF_LEN >= pay.length || pay[p + EF_LEN] !== 0) {
    throw new WalkError('event-flag terminator is not 0 - the walk went off the rails');
  }
  return {
    version,
    playerGameData,
    eventFlags: p,
    deaths,
    characterType,
    lastRestedGrace,
    regionCount,
  };
}

/** Stats block. Offsets are relative to PlayerGameData. */
function readCharacter(pay, w) {
  const g = w.playerGameData;
  const u32 = (o) => pay.readUInt32LE(o);
  let e = g + 0x94;
  const limit = e + 32;
  while (e + 1 < limit && pay.readUInt16LE(e) !== 0) e += 2;
  return {
    hp: u32(g + 0x08), maxHp: u32(g + 0x0c),
    fp: u32(g + 0x14), maxFp: u32(g + 0x18),
    stamina: u32(g + 0x24), maxStamina: u32(g + 0x28),
    vigor: u32(g + 0x34), mind: u32(g + 0x38), endurance: u32(g + 0x3c),
    strength: u32(g + 0x40), dexterity: u32(g + 0x44), intelligence: u32(g + 0x48),
    faith: u32(g + 0x4c), arcane: u32(g + 0x50),
    level: u32(g + 0x60),
    runes: u32(g + 0x64),
    runesMemory: u32(g + 0x68),
    name: pay.toString('utf16le', g + 0x94, e),
    deaths: w.deaths,
  };
}

function mapIdString(b) {
  return `m${String(b[3]).padStart(2, '0')}_${String(b[2]).padStart(2, '0')}_` +
         `${String(b[1]).padStart(2, '0')}_${String(b[0]).padStart(2, '0')}`;
}

/**
 * Player coordinates live after the bitfield, behind four more variable blocks.
 * This is the least-anchored part of the format, so failures are non-fatal.
 */
function readPosition(pay, w) {
  const i32 = (o) => pay.readInt32LE(o);
  let p = w.eventFlags + EF_LEN + 1;
  p += 4 + Math.max(0, i32(p));            // CSFieldArea
  p += 4 + Math.max(0, i32(p));            // CSWorldArea
  for (let k = 0; k < 2; k++) {            // CSWorldGeomMan x2 ('MOEG', 'FOEG')
    p += 4;
    p += 8;
    for (;;) {
      const esize = i32(p + 4);
      if (esize <= 0) { p += 16; break; }
      p += 16 + (esize - 0x10);
    }
  }
  p += 4 + Math.max(0, i32(p));            // CSRendMan
  const mid = pay.subarray(p + 12, p + 16);
  return {
    x: pay.readFloatLE(p),
    y: pay.readFloatLE(p + 4),
    z: pay.readFloatLE(p + 8),
    mapId: mapIdString(mid),
    mapBytes: [mid[0], mid[1], mid[2], mid[3]],
  };
}

/** Random access into the bitfield, given the block -> group table. */
class EventFlags {
  constructor(pay, offset, groups) {
    this.pay = pay;
    this.offset = offset;
    this.groups = groups;
  }

  get(flagId) {
    const block = Math.floor(flagId / FLAG_DIVISOR);
    const group = this.groups.get(block);
    if (group === undefined) return null;
    const index = flagId - block * FLAG_DIVISOR;
    const byte = this.offset + group * BLOCK_SIZE + (index >>> 3);
    if (byte >= this.pay.length) return null;
    return ((this.pay[byte] >> (7 - (index & 7))) & 1) === 1;
  }

  /** Set flag ids, for diffing two saves. */
  countSet() {
    let n = 0;
    for (const group of this.groups.values()) {
      const base = this.offset + group * BLOCK_SIZE;
      for (let i = 0; i < BLOCK_SIZE; i++) {
        let v = this.pay[base + i];
        while (v) { n += v & 1; v >>>= 1; }
      }
    }
    return n;
  }
}

module.exports = { walkSlot, readCharacter, readPosition, EventFlags, WalkError,
                   EF_LEN, FLAG_DIVISOR, BLOCK_SIZE, mapIdString };
