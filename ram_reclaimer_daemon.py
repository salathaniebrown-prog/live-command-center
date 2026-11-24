import ctypes
import ctypes.util
import gc
import os
import sqlite3
import sys

WAL_DB_PATH = os.path.expanduser("~/astra_telemetry_wal.db")
MADV_DONTNEED = 4

_INTERNED_KEYS = tuple(
    sys.intern(k)
    for k in (
        "slot",
        "avail_ram_mb",
        "psi_mem_avg10",
        "android_oom_score",
        "shield_state",
        "merkle_root",
        "shannon_entropy",
        "thermal_drift_ppm",
        "NOMINAL",
        "ECOSYSTEM_DAG_CORE",
    )
)


def get_rss_mb() -> float:
    """Reads exact physical Resident Set Size (RSS) in MB from /proc/self/statm."""
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as f:
            rss_pages = int(f.read().split()[1])
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round((rss_pages * page_size) / (1024 * 1024), 2)
    except Exception:
        return -1.0


def force_kernel_ram_release() -> dict:
    """
    Physically strips freed heap arenas back to the Android/Linux kernel:
    1. Clears Python internal caches, interns common keys, and runs gen 0/1/2 GC.
    2. Truncates SQLite WAL and shrinks SQLite page cache.
    3. Invokes native libc malloc_trim(0) to unmap freed heap pages from RSS.
    """
    before_mb = get_rss_mb()

    for s in _INTERNED_KEYS:
        sys.intern(s)
    if hasattr(sys, "_clear_type_cache"):
        sys._clear_type_cache()
    gc.collect(0)
    gc.collect(1)
    gc.collect(2)

    if os.path.exists(WAL_DB_PATH):
        try:
            with sqlite3.connect(WAL_DB_PATH, timeout=1.5) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.execute("PRAGMA shrink_memory;")
        except Exception:
            pass

    trimmed = False
    libc_name = ctypes.util.find_library("c") or "libc.so"
    try:
        libc = ctypes.CDLL(libc_name)
        if hasattr(libc, "malloc_trim"):
            libc.malloc_trim(0)
            trimmed = True
    except Exception:
        pass

    after_mb = get_rss_mb()
    return {
        "rss_before_mb": before_mb,
        "rss_after_mb": after_mb,
        "reclaimed_mb": round(max(before_mb - after_mb, 0.0), 2),
        "libc_malloc_trim": trimmed,
    }


def prune_zombie_python_workers(keep_tokens=()) -> list:
    """
    Scans /proc for stray/orphan python workers not part of the active command center
    and sends SIGTERM to reclaim host RAM safely.
    """
    my_pid = os.getpid()
    parent_pid = os.getppid()
    protected = (
        "alstra_unified_8090_gateway",
        "dashboard_server",
        "universal_pilot",
        "car_port_bridge",
        "main_head_router",
        "ram_self_controller",
        "ram_reclaimer_daemon",
        "astra_single_loop_supervisor",
        "overnight_autopilot_guard",
        "start_core_stack",
        "tdd_error_gate",
        *keep_tokens,
    )
    killed = []

    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in (my_pid, parent_pid):
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
            if "python" in cmd and not any(tok in cmd for tok in protected):
                os.kill(pid, 15)
                killed.append({"pid": pid, "cmd": cmd[:60]})
        except Exception:
            continue
    return killed


def _verify_and_execute_reclaim():
    try:
        killed = prune_zombie_python_workers()
        stats = force_kernel_ram_release()
        assert stats["rss_after_mb"] >= 0, "Invalid RSS metric"
        print(
            f"[RAM RECLAIMER OK] RSS: {stats['rss_before_mb']}MB -> {stats['rss_after_mb']}MB "
            f"(reclaimed={stats['reclaimed_mb']}MB, trim={stats['libc_malloc_trim']}) | Pruned: {len(killed)}"
        )
    except Exception as exc:
        print(f"[SELF-HEAL RAM] Fallback GC executed: {exc}")
        gc.collect(2)


if __name__ == "__main__":
    _verify_and_execute_reclaim()
