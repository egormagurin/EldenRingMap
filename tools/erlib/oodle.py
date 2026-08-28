"""Oodle (Kraken) decompression via the game's own oo2core_6_win64.dll.

Elden Ring's DCX payloads are Oodle-compressed. Rather than vendor a codec, we
call the DLL that ships with the game you already own. Nothing is redistributed.
"""
# Keeps the `X | None` annotations below from being evaluated, so this still
# imports on Python 3.9 - the floor the README promises.
from __future__ import annotations

import ctypes
import os
from collections.abc import Callable

_DLL_NAMES: tuple[str, ...] = (
    "oo2core_6_win64.dll", "oo2core_8_win64.dll", "oo2core_9_win64.dll")
_handle = None
_fn = None


def load(game_dir: str | None = None):
    """Load OodleLZ_Decompress. Returns the ctypes function."""
    global _handle, _fn
    if _fn is not None:
        return _fn

    if os.name != "nt":
        native = os.environ.get("ER_LINOODLE")
        if not native:
            raise RuntimeError(
                "native Oodle shim not configured; run setup-linux.sh")
        try:
            _handle = ctypes.CDLL(native)
        except OSError as exc:
            raise RuntimeError(
                f"could not load native Oodle shim {native}: {exc}") from exc
    else:
        candidates: list[str] = []
        if game_dir:
            candidates += [os.path.join(game_dir, n) for n in _DLL_NAMES]
        candidates += _DLL_NAMES          # also try the DLL search path

        last = None
        for path in candidates:
            try:
                _handle = ctypes.WinDLL(path)
                break
            except OSError as exc:
                last = exc
                _handle = None
        if _handle is None:
            raise RuntimeError(
                "could not load an Oodle DLL. Point --game-dir at the folder "
                + f"containing oo2core_6_win64.dll. Last error: {last}")

    fn = _handle.OodleLZ_Decompress
    fn.restype = ctypes.c_ssize_t
    fn.argtypes = [
        ctypes.c_void_p, ctypes.c_ssize_t,      # compBuf, compBufSize
        ctypes.c_void_p, ctypes.c_ssize_t,      # rawBuf, rawLen
        ctypes.c_int, ctypes.c_int, ctypes.c_int,   # fuzzSafe, checkCRC, verbosity
        ctypes.c_void_p, ctypes.c_ssize_t,      # decBufBase, decBufSize
        ctypes.c_void_p, ctypes.c_void_p,       # callback, callbackUserData
        ctypes.c_void_p, ctypes.c_ssize_t,      # decoderMemory, decoderMemorySize
        ctypes.c_int,                           # threadPhase
    ]
    _fn = fn
    return _fn


def decompress(
        payload: bytes,
        uncompressed_size: int,
        game_dir: str | None = None,
) -> bytes:
    fn = load(game_dir)
    out = ctypes.create_string_buffer(uncompressed_size)
    n = fn(payload, len(payload), out, uncompressed_size,
           1, 0, 0,          # fuzzSafe=Yes, checkCRC=No, verbosity=None
           None, 0, None, None, None, 0,
           3)                # threadPhase = unthreaded
    if n != uncompressed_size:
        raise RuntimeError(f"OodleLZ_Decompress returned {n}, expected {uncompressed_size}")
    return out.raw[:uncompressed_size]


def make_helper(game_dir: str) -> Callable[[bytes, int], bytes]:
    """Return a callable matching dcx.decompress(..., oodle=)."""
    def _oodle(payload: bytes, uncompressed_size: int) -> bytes:
        return decompress(payload, uncompressed_size, game_dir)
    return _oodle
