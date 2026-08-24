"""Read-only access to another process's memory (Windows).

Used to poll Elden Ring's live state. Nothing here writes: the process is
opened with PROCESS_VM_READ | PROCESS_QUERY_INFORMATION only, so it is not
capable of modifying the game even by accident.
"""
import ctypes
import ctypes.wintypes as w
import re
import struct

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
MAX_PATH = 260


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("th32ModuleID", w.DWORD), ("th32ProcessID", w.DWORD),
        ("GlblcntUsage", w.DWORD), ("ProccntUsage", w.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)), ("modBaseSize", w.DWORD),
        ("hModule", w.HMODULE), ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * MAX_PATH),
    ]


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
        ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_char * MAX_PATH),
    ]


k32.OpenProcess.restype = w.HANDLE
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.ReadProcessMemory.argtypes = [w.HANDLE, w.LPCVOID, w.LPVOID,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = w.BOOL
k32.CreateToolhelp32Snapshot.restype = w.HANDLE


def find_pid(exe_name: str):
    """PID of the first process with this image name, or None."""
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)   # TH32CS_SNAPPROCESS
    if snap == -1:
        return None
    try:
        e = PROCESSENTRY32()
        e.dwSize = ctypes.sizeof(e)
        if not k32.Process32First(snap, ctypes.byref(e)):
            return None
        while True:
            if e.szExeFile.decode("latin1").lower() == exe_name.lower():
                return e.th32ProcessID
            if not k32.Process32Next(snap, ctypes.byref(e)):
                return None
    finally:
        k32.CloseHandle(snap)


class ProcessNotFound(RuntimeError):
    pass


class Process:
    """A read-only handle onto a running process."""

    def __init__(self, exe_name="eldenring.exe", pid=None):
        self.exe_name = exe_name
        self.pid = pid or find_pid(exe_name)
        if not self.pid:
            raise ProcessNotFound(f"{exe_name} is not running")
        self.handle = k32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, self.pid)
        if not self.handle:
            raise ProcessNotFound(
                f"could not open {exe_name} (pid {self.pid}) - "
                f"error {ctypes.get_last_error()}. Try running as administrator.")
        self.base, self.size = self.module_info(exe_name)

    # ------------------------------------------------------------------ modules

    def module_info(self, name):
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.pid)
        if snap == -1:
            raise ProcessNotFound("module snapshot failed")
        try:
            m = MODULEENTRY32()
            m.dwSize = ctypes.sizeof(m)
            if not k32.Module32First(snap, ctypes.byref(m)):
                raise ProcessNotFound("Module32First failed")
            while True:
                if m.szModule.decode("latin1").lower() == name.lower():
                    return ctypes.cast(m.modBaseAddr, ctypes.c_void_p).value, m.modBaseSize
                if not k32.Module32Next(snap, ctypes.byref(m)):
                    raise ProcessNotFound(f"module {name} not found")
        finally:
            k32.CloseHandle(snap)

    # -------------------------------------------------------------------- reads

    def read(self, addr, size):
        """Bytes at `addr`, or None if the page is not readable."""
        if not addr:
            return None
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf,
                                   size, ctypes.byref(got))
        if not ok or got.value != size:
            return None
        return buf.raw

    def u64(self, addr):
        b = self.read(addr, 8)
        return struct.unpack("<Q", b)[0] if b else None

    def u32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack("<I", b)[0] if b else None

    def i32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack("<i", b)[0] if b else None

    def f32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack("<f", b)[0] if b else None

    def chain(self, base, offsets):
        """Follow a pointer chain: deref `base`, add each offset, deref again.

        The final offset is NOT dereferenced - it yields the address of the
        value you want. Returns None the moment any hop is unreadable, which is
        the normal case while the game is loading.
        """
        addr = self.u64(base)
        if not addr:
            return None
        for off in offsets[:-1]:
            addr = self.u64(addr + off)
            if not addr:
                return None
        return addr + offsets[-1]

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    # ------------------------------------------------------------------- AOB

    def scan(self, pattern: str, start=None, size=None):
        """First address matching an IDA-style byte pattern ('48 8B 0D ?? ??').

        Scans the main module's image by default. Patterns are used instead of
        hardcoded offsets because they survive most game patches.
        """
        rx = re.compile(pattern_to_regex(pattern), re.DOTALL)
        start = self.base if start is None else start
        size = self.size if size is None else size

        CHUNK = 4 << 20
        overlap = 64
        pos = 0
        while pos < size:
            n = min(CHUNK, size - pos)
            data = self.read(start + pos, n)
            if data:
                m = rx.search(data)
                if m:
                    return start + pos + m.start()
            pos += n - overlap if n == CHUNK else n
        return None

    def resolve_rip(self, instr_addr, instr_len=7, rel_at=3):
        """RIP-relative operand -> absolute address.

        `48 8B 05 xx xx xx xx` is `mov rax,[rip+rel32]`; the target is the
        address of the NEXT instruction plus the signed 32-bit displacement.
        """
        if not instr_addr:
            return None
        rel = self.i32(instr_addr + rel_at)
        if rel is None:
            return None
        return instr_addr + instr_len + rel


def pattern_to_regex(pattern: str) -> bytes:
    out = b""
    for tok in pattern.split():
        if tok in ("??", "?"):
            out += b"."
        else:
            out += re.escape(bytes([int(tok, 16)]))
    return out
