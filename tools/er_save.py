"""
Elden Ring ER0000.sl2 reader — event flags, character stats, position.

Verified against real saves (versions 130-252) and the ER-Save-Lib test corpus.

Sources:
  - ClayAmore/ER-Save-Lib  src/api/event_flags.rs      (flag id -> offset/bit algorithm)
  - ClayAmore/ER-Save-Lib  src/save/user_data_x.rs     (slot struct)
  - ClayAmore/ER-Save-Lib  src/res/eventflag_bst.txt   (block -> group table, 11920 entries)
  - ClayAmore/EldenRingSaveTemplate SL2.bt             (010 template, struct sizes)
  - BenGrn/EldenRingSaveCopier SaveGame.cs             (USER_DATA010 offsets)

NOTE: Elden Ring PC saves are NOT AES-encrypted. Each BND4 entry is
      [16-byte MD5 of the remaining bytes][plaintext payload].
"""

import hashlib
import os
import struct

EF_LEN = 0x1BF99F           # event-flag bitfield length in bytes (1,833,375)
FLAG_DIVISOR = 1000         # flags per block
BLOCK_SIZE = 125            # bytes per block (1000 bits / 8)

def _wstr(b, o, nbytes):
    """UTF-16LE, terminated at the first NUL wchar. The game does not clear the tail of
    the fixed-size buffer, so bytes after the terminator can be stale garbage."""
    raw = bytes(b[o:o + nbytes])
    for i in range(0, len(raw) - 1, 2):
        if raw[i] == 0 and raw[i + 1] == 0:
            raw = raw[:i]
            break
    return raw.decode("utf-16-le", "replace")


_u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
_i32 = lambda b, o: struct.unpack_from("<i", b, o)[0]
_u64 = lambda b, o: struct.unpack_from("<Q", b, o)[0]
_f32 = lambda b, o: struct.unpack_from("<f", b, o)[0]


# ---------------------------------------------------------------- BND4 container

def read_entries(data):
    """Return list of (data_offset, size) for the 12 BND4 entries.

    Entry headers start at 0x40, stride 0x20; size at +0x08 (i64), data offset at +0x10 (u32).
    For a standard PC ER0000.sl2 (28,967,888 bytes) this yields:
        entries 0..9  -> USER_DATA000..009, size 0x280010, first at 0x300
        entry  10     -> USER_DATA010 (profile/header summary), size 0x60010
        entry  11     -> USER_DATA011 (regulation),             size 0x240020
    """
    out = []
    for i in range(12):
        h = 0x40 + i * 0x20
        size = struct.unpack_from("<q", data, h + 0x08)[0]
        off = _u32(data, h + 0x10)
        out.append((off, size))
    return out


def verify_checksums(data):
    """True if every entry's leading 16 bytes equal md5(entry[16:]) (i.e. not encrypted)."""
    return all(
        hashlib.md5(data[o + 0x10:o + s]).digest() == data[o:o + 0x10]
        for o, s in read_entries(data)
    )


def fix_checksums(buf):
    """Recompute every entry's MD5 in place. Required after any edit or the game
    reports 'Corrupted Save Data'. `buf` must be a bytearray."""
    for o, s in read_entries(buf):
        buf[o:o + 0x10] = hashlib.md5(bytes(buf[o + 0x10:o + s])).digest()
    return buf


def slot_payload(data, index):
    """Decrypted (== plaintext) payload of USER_DATA00<index>, i.e. entry bytes after the MD5."""
    off, size = read_entries(data)[index]
    return data[off + 0x10:off + size]


# ---------------------------------------------- walk a slot payload to the event flags

def event_flags_offset(pay):
    """Payload-relative byte offset of the event-flag bitfield inside a slot.

    The offset is NOT constant: the gaitem map, projectile list and region list are
    variable-length, so every field before the bitfield must be walked. Observed range
    across the verified corpus: 0x367B7 .. 0x3C3D9.
    """
    version = _u32(pay, 0)
    p = 0x20                                    # u32 version, 4B map id, 0x18 unk

    # Gaitem map: 0x1400 entries (0x13FE on save version <= 81), VARIABLE stride
    for _ in range(0x1400 if version > 81 else 0x13FE):
        handle = _u32(pay, p)
        p += 8                                  # gaitem_handle + item_id
        if handle:
            top = handle & 0xF0000000
            if top == 0x80000000:               # weapon: +unk,unk,aow_handle,pad
                p += 13
            elif top == 0x90000000:             # armor: +unk,unk
                p += 8

    p += 0x1B0                                  # PlayerGameData
    p += 0xD * 0x10                             # SPEffect[13]
    p += 0x58                                   # EquippedItemsEquipIndex
    p += 0x1C                                   # ActiveWeaponSlotsAndArmStyle
    p += 0x58                                   # EquippedItemsItemId
    p += 0x58                                   # EquippedItemsGaitemHandle
    p += 4 + 0xA80 * 12 + 4 + 0x180 * 12 + 8    # InventoryHeld (2688 common / 384 key)
    p += 14 * 8 + 4                             # EquippedSpells
    p += 0xA * 8 + 4 + 6 * 8 + 8                # EquippedItems
    p += 6 * 4                                  # EquippedGestures
    p += 4 + _u32(pay, p) * 8                   # AcquiredProjectiles (VARIABLE)
    p += 0x27 * 4                               # EquippedArmamentsAndItems
    p += 0xC                                    # EquippedPhysics

    assert pay[p + 4:p + 8] in (b"FACE", b"\0\0\0\0"), "FaceData magic mismatch @0x%X" % p
    p += 0x12F                                  # FaceData (slot variant, 11-byte tail)

    p += 4 + 0x780 * 12 + 4 + 0x80 * 12 + 8     # InventoryStorageBox (1920 common / 128 key)
    p += 0x40 * 4                               # Gestures
    p += 4 + _u32(pay, p) * 4                   # Regions (VARIABLE)
    p += 0x28                                   # RideGameData (horse)
    assert pay[p] in (0, 1), "control byte @0x%X = %d" % (p, pay[p])
    p += 1
    p += 0x44                                   # BloodStain
    p += 8                                      # 2 unk u32
    p += 8 + _u32(pay, p + 4)                   # MenuProfileSaveLoad (VARIABLE, 8 + size)
    p += 0x34                                   # TrophyEquipData
    p += 8 + 7000 * 0x10                        # GaitemGameData (i64 count + 7000 * 0x10)

    tsize, tcount = _u32(pay, p + 4), _u32(pay, p + 8)
    p += 8 + (4 if tcount == 0 else 4 + ((tsize - 4) // 4) * 4)   # TutorialData

    p += 3                                      # gameman 0x8c / 0x8d / 0x8e
    p += 4                                      # total_deaths_count
    p += 4                                      # character_type (i32, -1 when offline)
    p += 1                                      # in_online_session_flag
    assert _u32(pay, p) in (0, 8), "character_type_online = %d" % _u32(pay, p)
    p += 4                                      # character_type_online
    p += 4                                      # last_rested_grace (grace entity id)
    p += 1                                      # not_alone_flag
    p += 4                                      # in_game_countdown_timer
    p += 4                                      # unk gamedataman 0x124/0x134

    assert pay[p + EF_LEN] == 0, "event-flag terminator is not 0"
    return p


# ---------------------------------------------------------------- event flags

def load_flag_groups(path):
    """Load eventflag_bst.txt -> {block: group}. 11,920 entries, groups 0..14297, all unique."""
    m = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                k, v = line.split(",")
                m[int(k)] = int(v)
    return m


class EventFlags:
    """Random access to the event-flag bitfield of one save slot."""

    def __init__(self, payload, groups, offset=None):
        self.pay = payload
        self.groups = groups
        self.offset = event_flags_offset(payload) if offset is None else offset

    def locate(self, flag_id):
        """flag_id -> (absolute payload byte offset, bit index) or None if the block
        does not exist (which means the id is not a real Elden Ring event flag)."""
        block, index = divmod(flag_id, FLAG_DIVISOR)
        group = self.groups.get(block)
        if group is None:
            return None
        byte = self.offset + group * BLOCK_SIZE + index // 8
        bit = 7 - (index % 8)               # MSB-first within the byte
        return byte, bit

    def get(self, flag_id):
        loc = self.locate(flag_id)
        if loc is None:
            return None
        byte, bit = loc
        return (self.pay[byte] >> bit) & 1

    def set(self, flag_id, on=True):
        """Requires `payload` to be a bytearray. Remember to fix_checksums() afterwards."""
        loc = self.locate(flag_id)
        if loc is None:
            raise KeyError("no flag block for id %d" % flag_id)
        byte, bit = loc
        if on:
            self.pay[byte] |= 1 << bit
        else:
            self.pay[byte] &= ~(1 << bit) & 0xFF

    def iter_set(self):
        """Yield every set flag id. ~1,700-6,600 for a real playthrough."""
        base = self.offset
        for block, group in self.groups.items():
            chunk = self.pay[base + group * BLOCK_SIZE: base + group * BLOCK_SIZE + BLOCK_SIZE]
            if not any(chunk):
                continue
            for i in range(FLAG_DIVISOR):
                if (chunk[i // 8] >> (7 - (i % 8))) & 1:
                    yield block * FLAG_DIVISOR + i


# ---------------------------------------------------------------- character data

def player_game_data_offset(pay):
    """Payload-relative offset of PlayerGameData (immediately after the gaitem map)."""
    version = _u32(pay, 0)
    p = 0x20
    for _ in range(0x1400 if version > 81 else 0x13FE):
        handle = _u32(pay, p)
        p += 8
        if handle:
            top = handle & 0xF0000000
            if top == 0x80000000:
                p += 13
            elif top == 0x90000000:
                p += 8
    return p


def read_character(pay):
    """Stats from the slot itself. Field offsets are relative to PlayerGameData."""
    g = player_game_data_offset(pay)
    mid = pay[4:8]
    return {
        "version": _u32(pay, 0),
        "map_id": "m%02d_%02d_%02d_%02d" % (mid[3], mid[2], mid[1], mid[0]),
        "hp": _u32(pay, g + 0x08), "max_hp": _u32(pay, g + 0x0C),
        "fp": _u32(pay, g + 0x14), "max_fp": _u32(pay, g + 0x18),
        "stamina": _u32(pay, g + 0x24), "max_stamina": _u32(pay, g + 0x28),
        "vigor": _u32(pay, g + 0x34), "mind": _u32(pay, g + 0x38),
        "endurance": _u32(pay, g + 0x3C), "strength": _u32(pay, g + 0x40),
        "dexterity": _u32(pay, g + 0x44), "intelligence": _u32(pay, g + 0x48),
        "faith": _u32(pay, g + 0x4C), "arcane": _u32(pay, g + 0x50),
        "level": _u32(pay, g + 0x60),
        "runes": _u32(pay, g + 0x64),
        "runes_memory": _u32(pay, g + 0x68),
        "name": _wstr(pay, g + 0x94, 32),
        "_player_game_data_offset": g,
    }


def read_position(pay):
    """Player coordinates + current map id, found by walking past the event-flag bitfield."""
    p = event_flags_offset(pay) + EF_LEN + 1          # skip bitfield + terminator

    p += 4 + max(0, _i32(pay, p))                     # CSFieldArea   {i32 size; data[size]}
    p += 4 + max(0, _i32(pay, p))                     # CSWorldArea   {i32 size; 'CHR ' ...}

    for _ in range(2):                                # CSWorldGeomMan x2 ('MOEG', 'FOEG')
        p += 4                                        # i32 size
        p += 8                                        # magic + unk
        while True:                                   # EntryData list, terminated by size <= 0
            esize = _i32(pay, p + 4)
            if esize <= 0:
                p += 16
                break
            p += 16 + (esize - 0x10)

    p += 4 + max(0, _i32(pay, p))                     # CSRendMan     {i32 size; data[size]}

    mid = pay[p + 12:p + 16]
    return {
        "x": _f32(pay, p), "y": _f32(pay, p + 4), "z": _f32(pay, p + 8),
        "map_id": "m%02d_%02d_%02d_%02d" % (mid[3], mid[2], mid[1], mid[0]),
        "map_id_bytes": tuple(mid),
        "angle": tuple(_f32(pay, p + 16 + 4 * i) for i in range(4)),
        "spawn_point_entity_id": _u32(pay, p + 0x3D + 2),
        "_player_coords_offset": p,
    }


# ---------------------------------------------------------------- USER_DATA010

PROFILE_STRIDE = 0x24C          # 588 bytes; matches EldenRingSaveCopier SAVE_HEADER_LENGTH


def read_profiles(data):
    """Parse USER_DATA010: the 10-slot summary shown on the load-game screen.

    Absolute offsets for a stock PC save (cross-checked against EldenRingSaveCopier):
        USER_DATA010 payload            0x19003B0
        active-profile bools (10 bytes) 0x1901D04
        profile[0]                      0x1901D0E, stride 0x24C
    """
    off, size = read_entries(data)[10]
    h = data[off + 0x10:off + size]

    p = 4 + 8                                   # u32 version, u64 steam_id
    p += 0x140                                  # CSSettings
    p += 8 + _u32(h, p + 4)                     # CSMenuSystemSaveLoad (VARIABLE, 8 + size)

    active = list(h[p:p + 10])
    p += 10

    profiles = []
    for i in range(10):
        b = p + i * PROFILE_STRIDE
        mid = h[b + 46:b + 50]
        profiles.append({
            "index": i,
            "active": bool(active[i]),
            "name": _wstr(h, b, 32),
            "level": _u32(h, b + 34),
            "seconds_played": _u32(h, b + 38),
            "runes_memory": _u32(h, b + 42),
            "map_id": "m%02d_%02d_%02d_%02d" % (mid[3], mid[2], mid[1], mid[0]),
            "_abs_offset": off + 0x10 + b,
        })
    return {
        "version": _u32(h, 0),
        "steam_id": _u64(h, 4),
        "profiles": profiles,
        "_profile_summary_offset": p - 10,
    }


# ---------------------------------------------------------------- demo

if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from erlib.gamepath import find_save

    save = sys.argv[1] if len(sys.argv) > 1 else find_save()
    if not save:
        sys.exit("No ER0000.sl2 found. Pass one: python tools/er_save.py <path>")
    bst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "eventflag_bst.txt")

    data = open(save, "rb").read()
    print("checksums valid (=> not encrypted):", verify_checksums(data))

    hdr = read_profiles(data)
    print("steam_id:", hdr["steam_id"])
    for pr in hdr["profiles"]:
        if pr["active"]:
            print("  slot %d  %-16r lvl %-4d %dh%02dm  %s" % (
                pr["index"], pr["name"], pr["level"],
                pr["seconds_played"] // 3600, (pr["seconds_played"] % 3600) // 60,
                pr["map_id"]))

    pay = slot_payload(data, 0)
    print("character:", read_character(pay))
    print("position :", read_position(pay))

    groups = load_flag_groups(bst)
    ef = EventFlags(pay, groups)
    print("event flags @ payload 0x%X, length 0x%X" % (ef.offset, EF_LEN))
    for fid, label in [(10000800, "Margit"), (10000802, "Godrick"),
                       (14000800, "Rennala"), (11000800, "Morgott"),
                       (76101, "grace: The First Step")]:
        print("  %-11d %-22s %s" % (fid, label, ef.get(fid)))
    print("total set flags:", sum(1 for _ in ef.iter_set()))
