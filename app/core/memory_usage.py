"""Numeric process-memory diagnostics; no environment, paths or source rows in logs."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)
STAGES = frozenset({"source_start", "source_ready", "inference_ready", "cache_ready", "failed"})


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
