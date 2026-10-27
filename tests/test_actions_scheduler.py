import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.persist_current_predictions import Client, OrchestrationError

KEY = "synthetic-actions-service-key-00000000"
READY = {
    "status": "ready",
    "model_ready": True,
    "artifact_integrity": "verified",
    "workload_identity_configured": True,
    "database_configured": True,
    "prediction_persistence_enabled": True,
}
SUMMARY = {"rows_evaluated": 100, "rows_inserted": 0, "rows_existing": 100}


def client_with(events):
    client = Client("https://api.example.org", KEY, sleep=Mock())
    client.request = Mock(side_effect=events)
    return client


def test_warm_health_and_ready_before_bounded_write_retries():
    client = client_with(
        [
            (503, None),
            (0, None),
            (200, {"status": "ok"}),
            (503, None),
            (200, READY),
            (504, None),
            (0, None),
            (200, SUMMARY),
        ]
    )
    result = client.run()
    assert result["status"] == "success_idempotent" and result["retry_count"] == 2
    assert [c.args[0] for c in client.request.call_args_list] == [
        "/health",
        "/health",
        "/health",
        "/ready",
        "/ready",
        *["/predictions/current/persist?limit=100"] * 3,
    ]
    assert [c.args[0] for c in client.sleep.call_args_list] == [30, 45, 30, 30, 60]


@pytest.mark.parametrize("stage", ["health", "ready", "persistence"])
@pytest.mark.parametrize("status", [400, 401, 403, 413, 422])
def test_nonretryable_statuses_fail_immediately(stage, status):
    preceding = {
        "health": [],
        "ready": [(200, {"status": "ok"})],
        "persistence": [(200, {"status": "ok"}), (200, READY)],
    }[stage]
    client = client_with([*preceding, (status, None)])
    with pytest.raises(OrchestrationError):
        client.run()
    assert client.request.call_count == len(preceding) + 1
    client.sleep.assert_not_called()


@pytest.mark.parametrize("stage", ["health", "ready", "persistence"])
def test_retry_exhaustion_is_bounded(stage):
    preceding = {
        "health": [],
        "ready": [(200, {"status": "ok"})],
        "persistence": [(200, {"status": "ok"}), (200, READY)],
    }[stage]
    client = client_with([*preceding, *[(503, None)] * 3])
    with pytest.raises(OrchestrationError):
        client.run()
    assert client.request.call_count == len(preceding) + 3


def test_ready_flags_must_be_real_booleans_and_verified():
    bad = {**READY, "database_configured": "true"}
    client = client_with([(200, {"status": "ok"}), *[(200, bad)] * 3])
    with pytest.raises(OrchestrationError):
        client.run()
    assert all(
        c.args[0] != "/predictions/current/persist?limit=100" for c in client.request.call_args_list
    )


def test_health_deadline_cannot_grow_past_120_seconds():
    client = client_with([(503, None)] * 3)
    times = iter([0, 0, 15, 45, 60, 105])
    client.clock = lambda: next(times)
    with pytest.raises(OrchestrationError):
        client.warm("/health", lambda d: True, "health")
    assert client.request.call_count <= 3
    assert sum(c.args[0] for c in client.sleep.call_args_list) <= 75


def test_history_failure_cannot_repeat_successful_write():
    client = client_with([(200, {"status": "ok"}), (200, READY), (200, SUMMARY), (503, None)])
    assert client.run(history=True)["history_followup_ok"] is False
    assert sum(c.kwargs.get("method") == "POST" for c in client.request.call_args_list) == 1


def test_response_headers_secrets_and_transport_sanitization():
    opener = Mock()
    response = Mock()
    response.status = 200
    response.headers = {}
    response.read1.side_effect = io.BytesIO(json.dumps(SUMMARY).encode()).read1
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener.open.return_value = response
    client = Client("https://api.example.org", KEY, opener=opener)
    assert client.request("/ready")[0] == 200
    request = opener.open.call_args.args[0]
    assert request.get_header("X-rmi-service-key") == KEY
    assert KEY not in request.full_url
    opener.open.side_effect = urllib.error.URLError("private-diagnostic")
    with pytest.raises(OrchestrationError) as error:
        client.request("/ready")
    assert "private" not in str(error.value)


def test_workflow_is_gated_minimal_and_only_calls_reviewed_client():
    text = Path(".github/workflows/persist-current-predictions.yml").read_text(encoding="utf-8")
    assert "cron: '17,47 * * * *'" in text and "workflow_dispatch:" in text
    assert "contents: read" in text and "write" not in text
    assert "RMI_ORCHESTRATION_ENABLED == 'true'" in text
    assert "cancel-in-progress: false" in text and "timeout-minutes: 15" in text
    assert "${{ secrets.RMI_API_BASE_URL }}" in text
    assert "${{ secrets.RMI_SERVICE_API_KEY }}" in text
    assert "python3 -m scripts.persist_current_predictions" in text
    assert not any(
        s in text.lower() for s in ("databricks", "postgres", "printenv", "curl -v", "pip install")
    )
