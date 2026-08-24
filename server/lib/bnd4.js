'use strict';
/**
 * BND4 container reader for Elden Ring save files (ER0000.sl2 / .sl2.bak / .co2).
 *
 * Layout verified empirically against a real 28,967,888-byte ER0000.sl2:
 *   0x00  "BND4"
 *   0x0C  uint32  fileCount            (12 for ER: 10 slots + header + misc)
 *   0x10  uint64  headerSize           (0x40)
 *   0x40  entry[fileCount], 32 bytes each:
 *           +0x00 uint64 flags         (0x50, then 0xFFFFFFFF padding)
 *           +0x08 uint64 size          (0x280010 per character slot)
 *           +0x10 uint32 dataOffset
 *           +0x14 uint32 nameOffset    -> UTF-16LE NUL-terminated name
 *
 * Each entry's data block is either:
 *   (a) PLAINTEXT: [16-byte MD5 of the remainder][payload]
 *   (b) ENCRYPTED: [16-byte AES IV][AES-128-CBC ciphertext]
 *       -> decrypts to [16-byte MD5 of the remainder][payload]
 *
 * We detect which by testing the MD5 on the raw bytes first. Vanilla Steam saves
 * are (b); saves that have passed through a save editor / manager are often (a).
 */
const crypto = require('crypto');

// Static AES-128 key used by Elden Ring for USER_DATA blocks in ER0000.sl2.
// Publicly documented; used by every open-source ER save tool.
const ER_SAVE_KEY = Buffer.from([
  0x18, 0xF6, 0x32, 0x66, 0x05, 0xBD, 0x17, 0x8A,
  0x55, 0x24, 0x52, 0x3A, 0xC0, 0xA0, 0xC6, 0x09,
]);

const MD5_LEN = 16;

function md5(buf) {
  return crypto.createHash('md5').update(buf).digest();
}

/** Parse the BND4 directory. Returns entry descriptors (no payload decoding). */
function readBnd4(buf) {
  if (buf.length < 0x40 || buf.toString('ascii', 0, 4) !== 'BND4') {
    throw new Error('Not a BND4 container (bad magic) - is this really an ER0000.sl2?');
  }
  const fileCount = buf.readUInt32LE(0x0c);
  if (fileCount <= 0 || fileCount > 256) {
    throw new Error(`BND4 fileCount out of range: ${fileCount}`);
  }
  const entries = [];
  for (let i = 0; i < fileCount; i++) {
    const o = 0x40 + i * 0x20;
    const size = Number(buf.readBigUInt64LE(o + 0x08));
    const dataOffset = buf.readUInt32LE(o + 0x10);
    const nameOffset = buf.readUInt32LE(o + 0x14);
    let e = nameOffset;
    while (e + 1 < buf.length && buf.readUInt16LE(e) !== 0) e += 2;
    entries.push({
      index: i,
      name: buf.toString('utf16le', nameOffset, e),
      size,
      dataOffset,
    });
  }
  return { fileCount, entries };
}

/**
 * Return the decrypted+verified payload of one entry (MD5 header stripped),
 * plus how it was stored.
 */
function readEntryPayload(buf, entry, key = ER_SAVE_KEY) {
  const block = buf.subarray(entry.dataOffset, entry.dataOffset + entry.size);
  if (block.length < MD5_LEN + 16) {
    throw new Error(`entry ${entry.name}: block too small (${block.length})`);
  }

  // (a) plaintext?
  const rawBody = block.subarray(MD5_LEN);
  if (md5(rawBody).equals(block.subarray(0, MD5_LEN))) {
    return { payload: rawBody, encrypted: false, checksumOk: true };
  }

  // (b) AES-128-CBC, IV = first 16 bytes.
  const iv = block.subarray(0, 16);
  const ct = block.subarray(16);
  let pt;
  try {
    const d = crypto.createDecipheriv('aes-128-cbc', key, iv);
    d.setAutoPadding(false);
    pt = Buffer.concat([d.update(ct), d.final()]);
  } catch (err) {
    throw new Error(`entry ${entry.name}: AES decrypt failed - ${err.message}`);
  }
  const body = pt.subarray(MD5_LEN);
  const checksumOk = md5(body).equals(pt.subarray(0, MD5_LEN));
  return { payload: body, encrypted: true, checksumOk };
}

/**
 * Re-pack a payload back into an entry, restoring the MD5 (and re-encrypting if
 * the source was encrypted). Only used by the (optional) snapshot tooling - the
 * live server NEVER writes to your save.
 */
function writeEntryPayload(buf, entry, payload, encrypted, key = ER_SAVE_KEY) {
  const body = Buffer.concat([md5(payload), payload]);
  if (!encrypted) {
    body.copy(buf, entry.dataOffset);
    return;
  }
  const iv = buf.subarray(entry.dataOffset, entry.dataOffset + 16);
  const c = crypto.createCipheriv('aes-128-cbc', key, iv);
  c.setAutoPadding(false);
  const ct = Buffer.concat([c.update(body), c.final()]);
  iv.copy(buf, entry.dataOffset);
  ct.copy(buf, entry.dataOffset + 16);
}

module.exports = { ER_SAVE_KEY, readBnd4, readEntryPayload, writeEntryPayload, md5 };
