"""Read-only access to a Wine/Proton process through Linux procfs."""
# `X | None` annotations, without requiring Python 3.10.
from __future__ import annotations

import os
import re
import struct
from collections.abc import Sequence
from pathlib import Path


class ProcessNotFound(RuntimeError):
    pass


def find_pid(exe_name: str) -> int | None:
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text().strip().lower() == exe_name.lower():
                return int(comm.parent.name)
        except OSError:
            continue
    return None


class Process:
    """A read-only procfs handle onto a running Wine/Proton process."""

    def __init__(self, exe_name: str = "eldenring.exe", pid: int | None = None):
        self.exe_name = exe_name
        self.pid = pid or find_pid(exe_name)
        if self.pid is None:
            raise ProcessNotFound(f"{exe_name} is not running")
        try:
            self._fd: int | None = os.open(f"/proc/{self.pid}/mem", os.O_RDONLY)
        except OSError as exc:
            raise ProcessNotFound(
                f"could not read {exe_name} (pid {self.pid}): {exc}") from exc
        self.base, self.size = self.module_info(exe_name)

    def module_info(self, name: str) -> tuple[int, int]:
        """Return the PE image base and SizeOfImage for `name`."""
        try:
            lines = Path(f"/proc/{self.pid}/maps").read_text().splitlines()
        except OSError as exc:
            raise ProcessNotFound(f"could not read maps for pid {self.pid}") from exc
        base = None
        for line in lines:
            parts = line.split(maxsplit=5)
            if len(parts) < 6 or parts[2] != "00000000":
                continue
            if Path(parts[5]).name.lower() == name.lower():
                base = int(parts[0].split("-", maxsplit=1)[0], 16)
                break
        if base is None:
            raise ProcessNotFound(f"module {name} not found in pid {self.pid}")
        header = self.read(base, 0x200)
        if header is None or header[:2] != b"MZ":
            raise ProcessNotFound(f"module {name} has no readable PE header")
        pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
        raw_size = self.read(base + pe_offset + 0x50, 4)
        if raw_size is None:
            raise ProcessNotFound(f"module {name} has no readable image size")
        return base, struct.unpack("<I", raw_size)[0]

    def read(self, addr: int, size: int) -> bytes | None:
        if addr == 0 or self._fd is None:
            return None
        try:
            data = os.pread(self._fd, size, addr)
        except OSError:
            return None
        return data if len(data) == size else None

    def u64(self, addr: int) -> int | None:
        data = self.read(addr, 8)
        return struct.unpack("<Q", data)[0] if data else None

    def u32(self, addr: int) -> int | None:
        data = self.read(addr, 4)
        return struct.unpack("<I", data)[0] if data else None

    def i32(self, addr: int) -> int | None:
        data = self.read(addr, 4)
        return struct.unpack("<i", data)[0] if data else None

    def f32(self, addr: int) -> float | None:
        data = self.read(addr, 4)
        return struct.unpack("<f", data)[0] if data else None

    def chain(self, base: int, offsets: Sequence[int]) -> int | None:
        """Follow a pointer chain, leaving the final offset undereferenced."""
        addr = self.u64(base)
        if addr is None:
            return None
        for offset in offsets[:-1]:
            addr = self.u64(addr + offset)
            if addr is None:
                return None
        return addr + offsets[-1]

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def scan(
            self,
            pattern: str,
            start: int | None = None,
            size: int | None = None,
    ) -> int | None:
        """Return the first address matching an IDA-style byte pattern."""
        regex = re.compile(pattern_to_regex(pattern), re.DOTALL)
        scan_start = self.base if start is None else start
        scan_size = self.size if size is None else size
        chunk_size = 4 << 20
        overlap = 64
        pos = 0
        while pos < scan_size:
            count = min(chunk_size, scan_size - pos)
            data = self.read(scan_start + pos, count)
            if data:
                match = regex.search(data)
                if match:
                    return scan_start + pos + match.start()
            pos += count - overlap if count == chunk_size else count
        return None

    def resolve_rip(
            self,
            instr_addr: int | None,
            instr_len: int = 7,
            rel_at: int = 3,
    ) -> int | None:
        """Resolve a RIP-relative operand to its absolute address."""
        if instr_addr is None:
            return None
        relative = self.i32(instr_addr + rel_at)
        if relative is None:
            return None
        return instr_addr + instr_len + relative


def pattern_to_regex(pattern: str) -> bytes:
    result = b""
    for token in pattern.split():
        result += b"." if token in ("??", "?") else re.escape(bytes([int(token, 16)]))
    return result
