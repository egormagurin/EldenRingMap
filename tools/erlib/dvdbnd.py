"""Elden Ring dvdbnd reader - pull individual files out of Data*.bhd/.bdt.

The game ships its content in split archives: a small `.bhd` header (RSA
encrypted) plus a multi-GB `.bdt` data slab. The header stores only a 64-bit
hash of each file's path, so you look files up by hashing the path you want.

Nothing here needs a secret: the `.bhd` "encryption" uses a *public* RSA key
with a large exponent, and each file's AES key is stored in the header itself.

Ported from SoulsFormatsNEXT `Formats/BHD5.cs` and UXM.
"""
import os
import struct
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES

from .archive_keys import ARCHIVE_KEYS

U64 = (1 << 64) - 1
PRIME64 = 0x85


def path_hash(path: str) -> int:
    """From's dvdbnd path hash: fold a normalised path with h = h*0x85 + c."""
    h = path.strip().replace(chr(92), "/").lower()
    if not h.startswith("/"):
        h = "/" + h
    acc = 0
    for ch in h:
        acc = (acc * PRIME64 + ord(ch)) & U64
    return acc


def decrypt_bhd(encrypted: bytes, pem: str) -> bytes:
    """Textbook-RSA decrypt a .bhd header. Each 256-byte block -> 255 bytes."""
    key = RSA.import_key(pem)
    n, e = key.n, key.e
    in_block = (n.bit_length() + 7) // 8
    out_block = in_block - 1
    if len(encrypted) % in_block:
        raise ValueError(f".bhd length {len(encrypted)} not a multiple of {in_block}")
    out = bytearray(len(encrypted) // in_block * out_block)
    for i in range(0, len(encrypted), in_block):
        c = int.from_bytes(encrypted[i:i + in_block], "big")
        m = pow(c, e, n)
        j = i // in_block * out_block
        out[j:j + out_block] = m.to_bytes(out_block, "big")
    return bytes(out)


class FileEntry:
    __slots__ = ("hash", "padded_size", "unpadded_size", "offset", "aes_key", "aes_ranges", "archive")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def size(self):
        return self.unpadded_size if self.unpadded_size > 0 else self.padded_size


def parse_bhd5(buf: bytes, archive: str = "") -> list:
    """Parse a DECRYPTED BHD5 header into its flat list of file entries."""
    if buf[:4] != b"BHD5":
        raise ValueError("not a BHD5 header (wrong key, or still encrypted?)")

    # 64-bit-field detection, same trick as BHD5.cs: two int32s must be zero.
    test0 = struct.unpack_from("<i", buf, 0x14)[0]
    test1 = struct.unpack_from("<i", buf, 0x1C)[0]
    is64 = test0 == 0 and test1 == 0

    p = 0x10
    if is64:
        bucket_count = struct.unpack_from("<q", buf, p)[0]; p += 8
        buckets_offset = struct.unpack_from("<q", buf, p)[0]; p += 8
    else:
        bucket_count = struct.unpack_from("<i", buf, p)[0]; p += 4
        buckets_offset = struct.unpack_from("<i", buf, p)[0]; p += 4
    salt_len = struct.unpack_from("<i", buf, p)[0]; p += 4
    # salt follows; unused

    buckets = []
    p = buckets_offset
    for _ in range(bucket_count):
        count = struct.unpack_from("<i", buf, p)[0]; p += 4
        if is64:
            p += 4                      # == 1
            off = struct.unpack_from("<q", buf, p)[0]; p += 8
        else:
            off = struct.unpack_from("<i", buf, p)[0]; p += 4
        buckets.append((count, off))

    entries = []
    for count, off in buckets:
        p = off
        for _ in range(count):
            h = struct.unpack_from("<Q", buf, p)[0]; p += 8
            padded = struct.unpack_from("<i", buf, p)[0]; p += 4
            unpadded = struct.unpack_from("<i", buf, p)[0]; p += 4
            data_off = struct.unpack_from("<q", buf, p)[0]; p += 8
            p += 8                      # sha hash offset (unused)
            aes_off = struct.unpack_from("<q", buf, p)[0]; p += 8

            aes_key, aes_ranges = None, None
            if aes_off:
                q = aes_off
                aes_key = buf[q:q + 16]; q += 16
                rc = struct.unpack_from("<i", buf, q)[0]; q += 4
                aes_ranges = []
                for _ in range(rc):
                    s = struct.unpack_from("<q", buf, q)[0]; q += 8
                    e2 = struct.unpack_from("<q", buf, q)[0]; q += 8
                    aes_ranges.append((s, e2))
            entries.append(FileEntry(hash=h, padded_size=padded, unpadded_size=unpadded,
                                     offset=data_off, aes_key=aes_key,
                                     aes_ranges=aes_ranges, archive=archive))
    return entries


def decrypt_aes_ranges(data: bytearray, key: bytes, ranges) -> None:
    """AES-128-ECB, no padding, over the header-specified byte ranges (in place)."""
    for start, end in ranges:
        if start < 0 or end < 0 or start == end:
            continue
        length = (end - start) & ~0xF          # ECB works on whole blocks
        if length <= 0:
            continue
        cipher = AES.new(key, AES.MODE_ECB)
        data[start:start + length] = cipher.decrypt(bytes(data[start:start + length]))


class DvdBnd:
    """Open the game's archives and read files out of them by path."""

    ARCHIVES = ["Data0", "Data1", "Data2", "Data3", "DLC", "DLC02"]

    def __init__(self, game_dir: str, cache_dir: str = None, verbose=True):
        self.game_dir = game_dir
        self.cache_dir = cache_dir
        self.verbose = verbose
        self.by_hash = {}
        self._open = {}
        self._load_all()

    def _log(self, *a):
        if self.verbose:
            print(*a)

    def _header_bytes(self, name):
        bhd = os.path.join(self.game_dir, name + ".bhd")
        if not os.path.exists(bhd):
            return None
        cached = None
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
            cached = os.path.join(self.cache_dir, name + ".bhd.dec")
            # The header is the archive's index - file hash -> offset in the .bdt.
            # A game patch rewrites both together, so a cache left over from
            # before the patch points at the wrong offsets and every read comes
            # back as plausible-looking garbage. Re-decrypt whenever the .bhd is
            # newer than the copy we cached from it.
            if os.path.exists(cached) and os.path.getmtime(cached) >= os.path.getmtime(bhd):
                with open(cached, "rb") as f:
                    return f.read()
            if os.path.exists(cached):
                self._log(f"  {name}: game has been patched, re-reading the archive index")
        pem = ARCHIVE_KEYS.get(name)
        if pem is None:
            self._log(f"  {name}: no RSA key, skipping")
            return None
        with open(bhd, "rb") as f:
            enc = f.read()
        dec = decrypt_bhd(enc, pem)
        if cached:
            with open(cached, "wb") as f:
                f.write(dec)
        return dec

    def _load_all(self):
        for name in self.ARCHIVES:
            try:
                dec = self._header_bytes(name)
            except Exception as exc:
                self._log(f"  {name}: header decrypt failed - {exc}")
                continue
            if dec is None:
                continue
            try:
                entries = parse_bhd5(dec, name)
            except Exception as exc:
                self._log(f"  {name}: BHD5 parse failed - {exc}")
                continue
            for e in entries:
                self.by_hash[e.hash] = e
            self._log(f"  {name}: {len(entries):,} files")

    def _bdt(self, archive):
        f = self._open.get(archive)
        if f is None:
            f = open(os.path.join(self.game_dir, archive + ".bdt"), "rb")
            self._open[archive] = f
        return f

    def has(self, path: str) -> bool:
        return path_hash(path) in self.by_hash

    def entry(self, path: str):
        return self.by_hash.get(path_hash(path))

    def read(self, path: str) -> bytes:
        e = self.entry(path)
        if e is None:
            raise KeyError(f"not in archives: {path}")
        return self.read_entry(e)

    def read_entry(self, e: FileEntry) -> bytes:
        f = self._bdt(e.archive)
        f.seek(e.offset)
        data = bytearray(f.read(e.padded_size))
        if e.aes_key:
            decrypt_aes_ranges(data, e.aes_key, e.aes_ranges)
        return bytes(data[:e.size])

    def close(self):
        for f in self._open.values():
            f.close()
        self._open.clear()
