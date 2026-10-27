import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.validate_n8n_workflow import BOUNDARY, WORKFLOW, validate, validate_boundary


@pytest.fixture
def workflow():
    return json.loads(WORKFLOW.read_text())


def test_sanitized_artifact_policy(workflow):
    validate(workflow)


@pytest.mark.parametrize(
    "change", ["active", "secret", "token", "code", "source", "credentials", "cycle"]
)
def test_policy_rejects_unsafe_mutation(workflow, change):
    if change == "active":
        workflow["active"] = True
    elif change == "secret":
        workflow["nodes"][0]["parameters"]["password"] = "must-never-export"
    elif change == "token":
        workflow["nodes"][0]["parameters"]["token"] = "must-never-export"
    elif change == "code":
        workflow["nodes"][0]["type"] = "n8n-nodes-base.code"
    elif change == "source":
        workflow["nodes"][0]["type"] = "n8n-nodes-base.postgres"
    elif change == "credentials":
        workflow["nodes"][0]["credentials"] = {"id": "private-reference"}
    else:
        workflow["connections"]["Manual Trigger"]["main"][0][0]["node"] = "Manual Trigger"
    with pytest.raises(ValueError):
        validate(workflow)


def responses():
    ready = {
        "model_ready": True,
        "artifact_integrity": "verified",
        "workload_identity_configured": True,
        "database_configured": True,
        "prediction_persistence_enabled": True,
    }
    persisted = {
        "source_watermark": "2026-10-27T00:00:00Z",
        "rows_evaluated": 100,
        "rows_inserted": 100,
        "rows_existing": 0,
        "model_version": "synthetic-model",
        "threshold": 0.2,
    }
    return {
        "/health": [{"statusCode": 200, "body": {"status": "ok"}}],
        "/ready": [{"statusCode": 200, "body": ready}],
        "/predictions/current/persist?limit=100": [{"statusCode": 200, "body": persisted}],
        "/predictions/history?limit=10": [
            {
                "statusCode": 200,
                "body": {
                    "rows": 10,
                    "predictions": [{"trip_id": "synthetic-row-must-not-reach-summary"}],
                },
            }
        ],
    }


def simulate(workflow, replies, **settings):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable; static validation still runs")
    workflow = copy.deepcopy(workflow)
    for node_config in workflow["nodes"]:
        if node_config["name"] == "FastAPI Configuration":
            node_config["parameters"]["assignments"]["assignments"][0]["value"] = settings.pop(
                "baseUrl", "https://backend.example.org"
            )
    result = subprocess.run(
        [node, str(Path(__file__).with_name("n8n_graph_harness.mjs"))],
        input=json.dumps({"workflow": workflow, "responses": replies, **settings}),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return json.loads(result.stdout)


def test_success_and_idempotent_replay_drop_rows(workflow):
    replies = responses()
    first = simulate(workflow, replies)
    assert first["summary"]["status"] == "success"
    assert first["summary"]["rows_inserted"] == 100
    assert first["summary"]["history_rows_returned"] == 10
    assert first["summary"]["retry_count"] == 0 and not first["waits"]
    assert "synthetic-row-must-not-reach-summary" not in json.dumps(first["summary"])
    body = replies["/predictions/current/persist?limit=100"][0]["body"]
    body.update(rows_inserted=0, rows_existing=100)
    second = simulate(workflow, replies, start="Schedule Every 15 Minutes")
    assert second["summary"]["status"] == "success_idempotent"
    assert second["summary"]["persistence_succeeded"] is True


@pytest.mark.parametrize("status", [503, 504])
def test_retry_exhaustion_is_exactly_two(workflow, status):
    replies = responses()
    replies["/predictions/current/persist?limit=100"] = [{"statusCode": status, "body": {}}]
    result = simulate(workflow, replies)
    assert result["summary"]["status"] == "persistence_failed"
    assert result["summary"]["retry_count"] == 2 and result["waits"] == [30, 60]
    assert sum(c["method"] == "POST" for c in result["calls"]) == 3
    assert all("history" not in c["endpoint"] for c in result["calls"])
    assert result["summary"]["rows_inserted"] is None


def test_recovery_after_both_backoffs(workflow):
    replies = responses()
    success = copy.deepcopy(replies["/predictions/current/persist?limit=100"][0])
    replies["/predictions/current/persist?limit=100"] = [
        {"statusCode": 503, "body": {}},
        {"statusCode": 504, "body": {}},
        success,
    ]
    result = simulate(workflow, replies)
    assert result["summary"]["status"] == "success" and result["summary"]["retry_count"] == 2
    assert result["waits"] == [30, 60]


@pytest.mark.parametrize("status", [400, 403, 413, 422, 500])
def test_non_retryable_status_no_wait(workflow, status):
    replies = responses()
    replies["/predictions/current/persist?limit=100"] = [{"statusCode": status, "body": {}}]
    result = simulate(workflow, replies)
    assert result["summary"]["status"] == "persistence_failed" and not result["waits"]
    assert sum(c["method"] == "POST" for c in result["calls"]) == 1


def test_ready_503_and_flags_stop_without_persistence(workflow):
    replies = responses()
    replies["/ready"][0]["statusCode"] = 503
    result = simulate(workflow, replies)
    assert result["summary"]["status"] == "not_ready"
    assert all(c["method"] != "POST" for c in result["calls"])
    replies["/ready"][0]["statusCode"] = 200
    for flag in (
        "model_ready",
        "artifact_integrity",
        "workload_identity_configured",
        "database_configured",
        "prediction_persistence_enabled",
    ):
        invalid = copy.deepcopy(replies)
        invalid["/ready"][0]["body"][flag] = False
        assert simulate(workflow, invalid)["summary"]["status"] == "not_ready"


def test_history_failure_keeps_persistence_success(workflow):
    replies = responses()
    replies["/predictions/history?limit=10"] = [{"statusCode": 503, "body": {}}]
    result = simulate(workflow, replies)
    assert result["summary"]["status"] == "history_followup_failed"
    assert result["summary"]["persistence_succeeded"] is True
    assert result["summary"]["rows_inserted"] == 100 and not result["waits"]


def test_health_failure_stops_before_ready(workflow):
    replies = responses()
    replies["/health"] = [{"statusCode": 503, "body": {}}]
    result = simulate(workflow, replies)
    assert result["summary"]["status"] == "health_unavailable"
    assert result["calls"] == [{"method": "GET", "endpoint": "/health"}]


@pytest.mark.parametrize("url", ["https://backend.example.org", "https://api.example.org:443"])
def test_configured_https_base_urls_are_supported(workflow, url):
    assert simulate(workflow, responses(), baseUrl=url)["summary"]["status"] == "success"


def test_transport_errors_never_echo_diagnostics(workflow):
    replies = responses()
    replies["/predictions/current/persist?limit=100"] = [{"error": "private-diagnostic"}]
    result = simulate(workflow, replies)
    assert result["summary"]["status"] == "persistence_failed" and not result["waits"]
    assert "private-diagnostic" not in json.dumps(result["summary"])


@pytest.mark.parametrize(
    "url",
    [
        "https://replace.invalid",
        "http://0.0.0.0:8000",
        "http://192.168.1.2:8000",
        "http://localhost:8000/extra",
        "http://localhost.evil:8000",
    ],
)
def test_insecure_api_url_rejected_before_http(workflow, url):
    result = simulate(workflow, responses(), baseUrl=url)
    assert result["summary"]["status"] == "configuration_rejected" and not result["calls"]


def test_webhook_builtin_auth_and_minimal_responses():
    boundary = json.loads(BOUNDARY.read_text())
    validate_boundary(boundary)
    boundary["nodes"][0]["parameters"]["authentication"] = "none"
    with pytest.raises(ValueError):
        validate_boundary(boundary)


@pytest.mark.parametrize("problem", [None, "extra", "event", "identifier", "time"])
def test_webhook_minimal_payload_after_native_auth(problem):
    boundary = json.loads(BOUNDARY.read_text())
    body = {
        "event": "prediction_orchestration_requested",
        "request_id": "00000000-0000-4000-8000-000000000000",
        "generated_at": "2026-10-27T12:00:00Z",
    }
    if problem == "extra":
        body["features"] = {"must_not": "be_forwarded"}
    elif problem == "event":
        body["event"] = "arbitrary-action"
    elif problem == "identifier":
        body["request_id"] = "invalid"
    elif problem == "time":
        body["generated_at"] = "not-a-time"
    result = simulate(
        boundary,
        {},
        start="Authenticated Webhook",
        authenticatedPayload={"body": body, "headers": {"private": "do-not-echo"}},
    )
    assert result["summary"]["http_status"] == (202 if problem is None else 400)
    assert result["summary"]["body"] == {"accepted": problem is None}
    assert not result["calls"] and "do-not-echo" not in json.dumps(result["summary"])
