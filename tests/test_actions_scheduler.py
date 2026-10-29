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
    client = client_with([*preceding, *[(503, None)] * (3 if stage == "persistence" else 5)])
    with pytest.raises(OrchestrationError):
        client.run()
    assert client.request.call_count == len(preceding) + (3 if stage == "persistence" else 5)


def test_ready_flags_must_be_real_booleans_and_verified():
    bad = {**READY, "database_configured": "true"}
    client = client_with([(200, {"status": "ok"}), *[(200, bad)] * 5])
    with pytest.raises(OrchestrationError):
        client.run()
    assert all(
        c.args[0] != "/predictions/current/persist?limit=100" for c in client.request.call_args_list
    )


class FakeClock:
    def __init__(self):
        self.now = 0
        self.delays = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.delays.append(seconds)
        self.now += seconds


@pytest.mark.parametrize("stage", ["health", "ready", "persistence"])
def test_real_elapsed_timeout_budget_and_no_write_before_readiness(stage):
    clock = FakeClock()
    client = Client("https://api.example.org", KEY, clock=clock, sleep=clock.sleep)

    def request(path, *, timeout, **kwargs):
        if path == "/health" and stage != "health":
            return 200, {"status": "ok"}
        if path == "/ready" and stage == "persistence":
            return 200, READY
        clock.now += timeout
        return 0, None

    client.request = Mock(side_effect=request)
    with pytest.raises(OrchestrationError, match=stage):
        client.run()
    assert clock.now == (510 if stage == "persistence" else 240)
    assert clock.delays == ([30, 60] if stage == "persistence" else [30, 45, 45, 45])
    if stage != "persistence":
        assert not any(c.kwargs.get("method") == "POST" for c in client.request.call_args_list)


def test_cold_start_recovers_after_old_deadline_with_shared_ready_budget():
    clock = FakeClock()
    client = Client("https://api.example.org", KEY, clock=clock, sleep=clock.sleep)

    def request(path, *, timeout, **kwargs):
        if path == "/health":
            clock.now += timeout
            return (200, {"status": "ok"}) if clock.now >= 180 else (0, None)
        if path == "/ready":
            clock.now += timeout
            return 200, READY
        return 200, SUMMARY

    client.request = Mock(side_effect=request)
    assert client.run()["retry_count"] == 0
    assert clock.now == 195
    assert client.request.call_args_list[-2].kwargs["timeout"] == 15


def test_ready_cannot_restart_shared_wake_deadline():
    clock = FakeClock()
    client = Client("https://api.example.org", KEY, clock=clock, sleep=clock.sleep)

    def request(path, *, timeout, **kwargs):
        clock.now += timeout
        if path == "/health" and clock.now >= 180:
            return 200, {"status": "ok"}
        return 0, None

    client.request = Mock(side_effect=request)
    with pytest.raises(OrchestrationError, match="ready"):
        client.run()
    assert clock.now <= 240
    assert not any(c.kwargs.get("method") == "POST" for c in client.request.call_args_list)


def test_total_wake_and_write_timeout_budget_remains_below_workflow_limit():
    clock = FakeClock()
    client = Client("https://api.example.org", KEY, clock=clock, sleep=clock.sleep)

    def request(path, *, timeout, **kwargs):
        if path == "/health":
            return 200, {"status": "ok"}
        clock.now += timeout
        if path == "/ready" and clock.now >= 240:
            return 200, READY
        return 0, None

    client.request = Mock(side_effect=request)
    with pytest.raises(OrchestrationError, match="persistence"):
        client.run()
    assert clock.now == 750 < 15 * 60
    assert sum(c.kwargs.get("method") == "POST" for c in client.request.call_args_list) == 3


@pytest.mark.parametrize("stage", [
    "configuration", "health", "ready", "persistence", "persistence_response",
    "transport", "response", "internal", "https://private.example/SECRET", None,
])
def test_main_logs_fixed_safe_stage_only(stage, monkeypatch, capsys):
    from scripts import persist_current_predictions as module

    monkeypatch.setenv("RMI_API_BASE_URL", "https://api.example.org")
    monkeypatch.setenv("RMI_SERVICE_API_KEY", KEY)
    monkeypatch.setattr(Client, "run", Mock(side_effect=OrchestrationError(stage)))
    expected = stage if stage in module.SAFE_STAGES else "internal"
    with pytest.raises(SystemExit) as error:
        module.main()
    assert str(error.value) == f"Prediction orchestration failed: {expected}"
    assert capsys.readouterr() == ("", "")


def test_main_unexpected_exception_never_prints_raw_diagnostics(monkeypatch, capsys):
    from scripts import persist_current_predictions as module

    monkeypatch.setattr(module, "Client", Mock(side_effect=RuntimeError(KEY + " private-url")))
    with pytest.raises(SystemExit) as error:
        module.main()
    assert str(error.value) == "Prediction orchestration failed: internal"
    assert capsys.readouterr() == ("", "")


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


def test_low_code_architecture_is_community_oci_and_actions_is_fallback():
    documents = [
        "README.md",
        "docs/ARCHITECTURE.md",
        "docs/N8N_CLOUD_ORCHESTRATION.md",
        "docs/SECURE_DEPLOYMENT.md",
        "docs/ZERO_COST_DEPLOYMENT.md",
        "docs/RUNTIME_SECURITY.md",
    ]
    for name in documents:
        text = Path(name).read_text(encoding="utf-8")
        required = (
            (
                "n8n Community Edition su OCI Always Free",
                "Deployment preparato; provisioning non ancora eseguito.",
                "Un solo scheduler attivo alla volta",
            )
            if name == "README.md"
            else (
                "n8n Community Edition on OCI Always Free",
                "SELECTED / DEPLOYMENT PREPARED / NOT YET PROVISIONED",
                "ONLY ONE scheduler active at a time",
            )
        )
        for statement in required:
            assert statement in text, name
        assert "GitHub Actions: zero-cost fallback scheduler" in text, name
        assert "0 EUR" in text, name
        normalized = " ".join(text.lower().split())
        for obsolete in (
            "github actions is the production orchestrator",
            "github actions is the proposed production orchestrator",
            "optional / demo / user-provided external orchestrator",
            "the production candidate uses github actions",
        ):
            assert obsolete not in normalized, name
    for name in (
        "app/integrations/n8n_client.py",
        "ops/n8n/workflows/rome_mobility_orchestration.json",
        "ops/n8n/workflows/rome_mobility_webhook_boundary.json",
        "docs/N8N_CLOUD_ORCHESTRATION.md",
    ):
        assert Path(name).is_file()
    zero_cost = Path("docs/ZERO_COST_DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "Make Free is second choice at degraded" in zero_cost
    assert "No candidate is selected in this PR" not in zero_cost
    workflow = Path(".github/workflows/persist-current-predictions.yml").read_text(encoding="utf-8")
    assert "zero-cost fallback" in workflow
    assert "RMI_ORCHESTRATION_ENABLED == 'true'" in workflow
