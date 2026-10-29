"""Opt-in read-only benchmark. Uses existing env settings; never serves HTTP or persists data."""

import argparse
import asyncio
import ctypes
import hashlib
import json
import subprocess
import sys
import time
import types

from pydantic import SecretStr

from app.contracts.public import PageQuery
from app.core.config import Settings
from app.data.databricks_client import DatabricksClient
from app.data.public_geography import PublicGeography
from app.main import create_app

BASELINE = "9536093"


def peak_mib():
    if sys.platform != "win32":
        import resource

        scale = 1048576 if sys.platform == "darwin" else 1024
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / scale
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    counter = Counters()
    counter.cb = ctypes.sizeof(counter)
    handle = ctypes.windll.kernel32.GetCurrentProcess
    handle.restype = wintypes.HANDLE
    api = ctypes.windll.psapi.GetProcessMemoryInfo
    api.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not api(handle(), ctypes.byref(counter), counter.cb):
        raise RuntimeError("Process memory measurement failed")
    return counter.PeakWorkingSetSize / 1048576


def reference(path):
    code = subprocess.check_output(
        ["git", "show", BASELINE + ":" + path],
        text=True,
        encoding="utf-8",
        stderr=subprocess.DEVNULL,
    )
    module = types.ModuleType("reviewed_memory_reference")
    exec(compile(code, path, "exec"), module.__dict__)
    return module


async def run(cfg, *, baseline=False):
    # This benchmark never needs the history database or persistence credentials.
    cfg = cfg.model_copy(
        update={"database_url": SecretStr(""), "enable_prediction_persistence": False}
    )
    application = create_app(cfg)
    async with application.router.lifespan_context(application):
        if baseline:
            repo = reference("app/data/current_repository.py").CurrentScoringRepository
            population = reference("app/services/public_population.py").PublicPopulation
            application.state.public_population = population(
                repo(DatabricksClient(cfg), cfg), lambda: application.state.model, PublicGeography()
            )
        service = application.state.public_population
        started = time.monotonic()
        startup = peak_mib()
        summary = service.summary()
        first = peak_mib()
        for order in ("risk_desc", "delay_desc", "route_asc", "time_desc"):
            page = service.page(PageQuery(page=2, page_size=50, sort=order))
            page.model_dump_json()
        measured = peak_mib()
        # Digest every probability, decision and observed value for before/after parity.
        # Compute only AFTER recording the process peak, without exporting any source rows.
        digest = hashlib.sha256()
        for item, _ in service._snapshot[0]:
            digest.update(
                repr(
                    (
                        item.observation_id,
                        item.major_delay_probability,
                        item.predicted_major_delay,
                        item.observed_current_delay_seconds,
                    )
                ).encode()
            )
        result = dict(
            variant=BASELINE if baseline else "working_tree",
            rows=summary.scored_count,
            routes=summary.route_count,
            watermark=str(summary.source_watermark),
            startup_peak_mib=round(startup, 2),
            first_peak_mib=round(first, 2),
            with_pages_peak_mib=round(measured, 2),
            seconds=round(time.monotonic() - started, 2),
            major_count=summary.major_delay_count,
            median=summary.median_observed_delay_seconds,
            p90=summary.p90_observed_delay_seconds,
            probability_digest=digest.hexdigest(),
            measurement="PeakWorkingSetSize" if sys.platform == "win32" else "ru_maxrss",
        )
        print(json.dumps(result))
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(Settings(_env_file=None), baseline=args.baseline))
    except Exception as error:
        # No exception bodies, connection strings or rejected input in diagnostics.
        print(json.dumps({"benchmark": "failed", "error_type": type(error).__name__}))
        raise SystemExit(1) from None
