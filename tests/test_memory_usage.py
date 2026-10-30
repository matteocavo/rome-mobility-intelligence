import logging
import subprocess
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.core.memory_usage import log_memory, reclaim_unused_memory


def test_memory_diagnostics_are_numeric_and_do_not_log_process_details(caplog):
    with (
        patch(
            "app.core.memory_usage.Path.read_text",
            return_value=("Name:\tprivate-process\nVmRSS:\t100 kB\nVmHWM:\t120 kB\n"),
        ),
        caplog.at_level(logging.INFO),
    ):
        log_memory("source_ready")
    assert "rss_bytes=102400 peak_rss_bytes=122880" in caplog.text
    assert "private-process" not in caplog.text


def test_memory_diagnostics_are_optional_and_reject_unreviewed_stages(caplog):
    with (
        patch("app.core.memory_usage.Path.read_text", side_effect=OSError),
        caplog.at_level(logging.INFO),
    ):
        log_memory("source_ready")
        log_memory("private-stage")
    assert not caplog.records


def test_reclaim_collects_before_native_trim_and_uses_only_process_library():
    events = []
    trim = Mock(side_effect=lambda pad: events.append(("trim", pad)))
    with (
        patch("app.core.memory_usage.sys.platform", "linux"),
        patch("app.core.memory_usage.gc.collect", side_effect=lambda: events.append("gc")),
        patch("app.core.memory_usage.ctypes.CDLL", return_value=SimpleNamespace(malloc_trim=trim))
        as library,
        patch("app.core.memory_usage.log_memory") as log,
    ):
        reclaim_unused_memory()
    assert events == ["gc", ("trim", 0)]
    library.assert_called_once_with(None)
    assert [call.args[0] for call in log.call_args_list] == ["reclaim_before", "reclaim_after"]
    assert len(trim.argtypes) == 1 and trim.restype is not None


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_reclaim_on_unsupported_platform_collects_without_loading_native_code(platform):
    with (
        patch("app.core.memory_usage.sys.platform", platform),
        patch("app.core.memory_usage.gc.collect") as collect,
        patch("app.core.memory_usage.ctypes.CDLL") as library,
    ):
        reclaim_unused_memory()
    collect.assert_called_once()
    library.assert_not_called()


@pytest.mark.parametrize("failure", [OSError("private-path"), AttributeError("private-symbol")])
def test_missing_native_trim_cannot_fail_serving_or_log_private_details(failure, caplog):
    with (
        patch("app.core.memory_usage.sys.platform", "linux"),
        patch("app.core.memory_usage.ctypes.CDLL", side_effect=failure),
        patch("app.core.memory_usage.log_memory"),
    ):
        reclaim_unused_memory()
    assert "private" not in caplog.text


@pytest.mark.skipif(sys.platform != "linux", reason="Real glibc RSS verification runs in Linux CI")
def test_linux_reclaims_freed_thread_heap_without_touching_live_allocations():
    # Isolate the allocator and RSS measurement from pytest and other tests. A
    # live tail allocation prevents automatic top-of-heap trimming: this tests
    # actual release of interior free pages, including a query worker's arena.
    script = textwrap.dedent("""
        import ctypes, json, threading
        from pathlib import Path
        from app.core.memory_usage import reclaim_unused_memory

        libc = ctypes.CDLL(None)
        if not hasattr(libc, 'malloc_trim'):
            raise SystemExit(77)
        libc.malloc.argtypes = [ctypes.c_size_t]
        libc.malloc.restype = ctypes.c_void_p
        libc.free.argtypes = [ctypes.c_void_p]
        live = []
        def prepare():
            blocks = [libc.malloc(8192) for _ in range(8192)]
            assert all(blocks)
            for pointer in blocks:
                ctypes.memset(pointer, 42, 8192)
            live.append(blocks.pop())
            for pointer in blocks:
                libc.free(pointer)
        worker = threading.Thread(target=prepare)
        worker.start()
        worker.join()
        def rss():
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) * 1024
            raise AssertionError('RSS unavailable')
        before = rss()
        reclaim_unused_memory()
        after = rss()
        assert ctypes.string_at(live[0], 8192) == bytes([42]) * 8192
        libc.free(live.pop())
        print(json.dumps({'before': before, 'after': after}))
        assert before - after >= 16 * 1024 * 1024, (before, after)
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    if result.returncode == 77:
        pytest.skip("This Linux libc has no malloc_trim")
    assert result.returncode == 0, result.stdout + result.stderr
