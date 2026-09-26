"""Size a run to the machine it is running on. Stdlib only."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass

_GB = 1024 ** 3
_BASE_WALK_FILES = 20_000
_BASE_WALK_BYTES = 200_000_000
_BASE_FILE_BYTES = 1_000_000
_BASE_CACHE = 64_000_000
_BASE_RUN_S = 600
_BASE_COVERAGE_S = 180


class TempSpaceError(RuntimeError):
    """The temp volume does not have enough free space for a working copy."""


@dataclass(frozen=True)
class HostBudget:
    cpu: int
    ram_bytes: int
    free_temp_bytes: int
    walk_files: int
    walk_bytes: int
    file_bytes: int
    cache_bytes: int
    run_budget_s: int
    coverage_timeout_s: int
    parse_workers: int
    allow_deep: bool
    temp_ok: bool
    note: str

    @classmethod
    def baseline(cls) -> HostBudget:
        """Today's caps: a 4-core, 8 GB machine with room on the temp volume."""
        return cls.for_machine(cpu=4, ram_bytes=8 * _GB, free_temp_bytes=10 * _GB)

    @classmethod
    def for_machine(cls, *, cpu: int, ram_bytes: int, free_temp_bytes: int) -> HostBudget:
        cpu = max(1, int(cpu))
        ram_bytes = max(0, int(ram_bytes))
        free_temp_bytes = max(0, int(free_temp_bytes))
        walk_files = _BASE_WALK_FILES
        walk_bytes = _BASE_WALK_BYTES
        cache_bytes = _BASE_CACHE
        run_budget_s = _BASE_RUN_S
        workers = 1
        allow_deep = True
        if ram_bytes < 2 * _GB:
            allow_deep = False
            walk_files //= 2
            walk_bytes //= 2
            cache_bytes //= 2
            run_budget_s //= 2
            note = (
                f"Host budget: {cpu} cores, {ram_bytes / _GB:.1f} GB RAM. "
                "Deep probes were not started because RAM is under 2 GB. "
                "Coverage still runs when --dynamic is set."
            )
        elif ram_bytes < 4 * _GB:
            walk_files //= 2
            walk_bytes //= 2
            cache_bytes //= 2
            run_budget_s //= 2
            note = (
                f"Host budget: {cpu} cores, {ram_bytes / _GB:.1f} GB RAM. "
                "Walk, cache, and the run budget are half of the 8 GB baseline. Deep probes still run."
            )
        elif cpu >= 8 and ram_bytes >= 16 * _GB:
            walk_files = 40_000
            cache_bytes = 128_000_000
            workers = min(8, cpu)
            note = (
                f"Host budget: {cpu} cores, {ram_bytes / _GB:.1f} GB RAM. "
                f"Walk cap is {walk_files} files, cache is 128 MB, parse workers are {workers}."
            )
        else:
            note = (
                f"Host budget: {cpu} cores, {ram_bytes / _GB:.1f} GB RAM. "
                f"Baseline caps: walk {walk_files} files / {walk_bytes // 1_000_000} MB, "
                f"cache {cache_bytes // 1_000_000} MB, run {run_budget_s}s, parse workers {workers}."
            )
        temp_ok = free_temp_bytes >= _GB
        if not temp_ok:
            note += (
                f" Temp volume has {free_temp_bytes / _GB:.2f} GB free, under 1 GB. "
                "Temp copies were not started."
            )
        return cls(
            cpu=cpu,
            ram_bytes=ram_bytes,
            free_temp_bytes=free_temp_bytes,
            walk_files=walk_files,
            walk_bytes=walk_bytes,
            file_bytes=_BASE_FILE_BYTES,
            cache_bytes=cache_bytes,
            run_budget_s=run_budget_s,
            coverage_timeout_s=_BASE_COVERAGE_S,
            parse_workers=workers,
            allow_deep=allow_deep,
            temp_ok=temp_ok,
            note=note,
        )

    @classmethod
    def detect(cls) -> HostBudget:
        if os.environ.get("RECOVERAGE_BUDGET") == "baseline":
            return cls.baseline()
        return cls.for_machine(cpu=_cpu(), ram_bytes=_ram_bytes(), free_temp_bytes=_free_temp())


def assert_temp_space(budget: HostBudget | None = None) -> None:
    chosen = budget or HostBudget.detect()
    if not chosen.temp_ok:
        raise TempSpaceError(chosen.note)


def _cpu() -> int:
    return os.cpu_count() or 1


def _free_temp() -> int:
    try:
        return int(shutil.disk_usage(tempfile.gettempdir()).free)
    except OSError:
        return 10 * _GB


def _ram_bytes() -> int:
    try:
        if os.name == "nt":
            return _ram_windows()
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and size > 0:
            return int(pages) * int(size)
    except (OSError, ValueError, AttributeError):
        pass
    return 8 * _GB


def _ram_windows() -> int:
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = (
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        )

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 8 * _GB
    return int(status.ullTotalPhys) or 8 * _GB
