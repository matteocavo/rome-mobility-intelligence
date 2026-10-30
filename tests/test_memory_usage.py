import logging
from unittest.mock import patch

from app.core.memory_usage import log_memory


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
