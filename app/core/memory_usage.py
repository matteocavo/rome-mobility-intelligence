"""Numeric process-memory diagnostics; no environment, paths or source rows in logs."""

import ctypes
import gc
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
STAGES = frozenset({
    "source_start", "source_ready", "inference_ready", "cache_ready", "failed",
    "reclaim_before", "reclaim_after",
})


def reclaim_unused_memory():
    """Return free glibc heap pages at population rebuild boundaries only.

    Collecting Python objects does not require the native allocator to return
    freed pages to the OS. malloc_trim releases only already-free pages, never
    live model/cache/reader data. It is optional on platforms without the symbol;
    no allocator, query budget or application data is replaced.
    """
    gc.collect()
    if sys.platform != "linux":
        return
    log_memory("reclaim_before")
    try:
        trim = ctypes.CDLL(None).malloc_trim
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        trim(0)
    except (AttributeError, OSError):
        pass  # Non-glibc Linux builds keep their existing allocation behavior.
    log_memory("reclaim_after")


def log_memory(stage):
    if stage not in STAGES:
        return
    values = {}
    try:
        # Linux/Render exposes current RSS and lifetime peak without a dependency.
        for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
            key, _, value = line.partition(":")
            if key in {"VmRSS", "VmHWM"}:
                values[key] = int(value.split()[0]) * 1024
    except (OSError, ValueError):
        return  # Unsupported platforms must not change serving behavior.
    logger.info(
        "serving_memory stage=%s rss_bytes=%d peak_rss_bytes=%d",
        stage,
        values.get("VmRSS", -1),
        values.get("VmHWM", -1),
    )
