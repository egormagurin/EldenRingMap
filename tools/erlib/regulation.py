"""Elden Ring regulation.bin -> decrypted, decompressed BND4 bytes.

regulation.bin is AES-256-CBC encrypted (IV = first 16 bytes of the file,
no padding on decrypt), wrapping a DCX-compressed BND4 of .param files.
Key is the publicly documented Elden Ring regulation key.
"""
from Crypto.Cipher import AES
from . import dcx

ER_REGULATION_KEY = bytes.fromhex(
    "99BFFC366A6BC8C6F5827D093602D676C42892A01C207FB024D3AF4E493FEF99"
)

def decrypt(path: str) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    iv, ct = data[:16], data[16:]
    ct = ct[: len(ct) - (len(ct) % 16)]
    plain = AES.new(ER_REGULATION_KEY, AES.MODE_CBC, iv).decrypt(ct)
    return plain

def load(path: str) -> bytes:
    """Return the decrypted + decompressed BND4 bytes."""
    return dcx.decompress(decrypt(path))
