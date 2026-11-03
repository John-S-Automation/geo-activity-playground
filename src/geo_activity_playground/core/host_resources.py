import os
import pathlib
import sys

MEMORY_PER_WORKER = 400 * 1024**2
MAX_DEFAULT_WORKERS = 4

_CGROUP_V2_LIMIT = pathlib.Path("/sys/fs/cgroup/memory.max")
_CGROUP_V1_LIMIT = pathlib.Path("/sys/fs/cgroup/memory/limit_in_bytes")


def available_memory() -> int | None:
    """Memory available to this process, honoring container limits."""
    for path in (_CGROUP_V2_LIMIT, _CGROUP_V1_LIMIT):
        try:
            content = path.read_text().strip()
        except OSError:
            continue
        if content == "max":
            break
        try:
            limit = int(content)
        except ValueError:
            continue
        # Cgroup v1 reports an absurdly large number instead of "max".
        if limit < 2**62:
            return limit
        break

    return _physical_memory()


def _physical_memory() -> int | None:
    if sys.platform == "win32":
        return _windows_physical_memory()
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None


def _windows_physical_memory() -> int | None:
    """Total physical memory via `GlobalMemoryStatusEx`, as Windows lacks `os.sysconf`."""
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullTotalPhys


def default_worker_count() -> int:
    """Worker processes that fit into the available CPU cores and memory."""
    candidates = [MAX_DEFAULT_WORKERS]
    if cpus := os.cpu_count():
        candidates.append(cpus)
    if memory := available_memory():
        candidates.append(memory // MEMORY_PER_WORKER)
    return max(1, min(candidates))
