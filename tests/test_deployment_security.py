import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deployment import validate_deployment
from app.core.http_security import HttpSecurity, RateBudgets
from app.core.service_auth import PROTECTED_PATHS, ServiceAuthError, verify_service_key
from app.main import create_app
from tests.conftest import SERVICE_KEY
from tests.test_inference_api import api as api
from tests.test_inference_api import row as row


@pytest.mark.parametrize(
    "path,method",
    [
        ("/predict", "post"),
        ("/predict/batch", "post"),
        ("/predictions/current", "get"),
        ("/predictions/history", "get"),
        ("/predictions/current/persist", "post"),
        ("/model/info", "get"),
    ],
)
def test_all_operational_endpoints_require_service_auth(api, path, method):
    api.headers.pop("X-RMI-Service-Key")
    call = getattr(api, method)
    assert call(path).status_code == 401
    assert call(path, headers={"X-RMI-Service-Key": "wrong"}).status_code == 401
    assert call(path, headers={"X-RMI-Service-Key": "S" * 300}).status_code == 401


def test_correct_service_auth_and_timing_safe_compare(api, row, monkeypatch):
    import hmac

    original = hmac.compare_digest
    compare = Mock(wraps=original)
    monkeypatch.setattr("app.core.service_auth.hmac.compare_digest", compare)
    assert api.post("/predict", json=row).status_code == 200
    assert compare.called
    assert api.get("/model/info").status_code == 200


def test_no_auth_or_body_side_effects_on_public_persistence_attempt(api):
    source = Mock()
    api.app.state.current_repository = source
    api.headers.pop("X-RMI-Service-Key")
    assert api.post("/predictions/current/persist").status_code == 401
    source.latest.assert_not_called()


def test_public_ready_minimized_and_service_ready_complete(api):
    public = api.get("/ready", headers={"X-RMI-Service-Key": "wrong"})
    assert public.status_code == 401
    api.headers.pop("X-RMI-Service-Key")
    assert api.get("/ready").json() == {"status": "ready"}
    detail = api.get("/ready", headers={"X-RMI-Service-Key": SERVICE_KEY})
    assert detail.status_code == 200
    assert detail.json()["model_ready"] and detail.json()["artifact_integrity"] == "verified"
    assert detail.json()["databricks_readiness"] == "not_checked"


def test_service_key_must_not_reuse_webhook_secret():
    cfg = Settings(_env_file=None, n8n_service_api_key=SERVICE_KEY, n8n_webhook_secret=SERVICE_KEY)
    with pytest.raises(ServiceAuthError):
        verify_service_key(cfg, SERVICE_KEY)
    with pytest.raises(RuntimeError, match="Deployment configuration"):
        create_app(cfg)


def test_inference_read_and_write_budgets_are_separate():
    cfg = Settings(_env_file=None, rate_limit_inference=1, rate_limit_write=1, rate_limit_read=1)
    clock = [0.0]
    rates = RateBudgets(cfg, clock=lambda: clock[0])
    assert rates.admit("inference") == 0
    assert rates.admit("inference") == 60
    assert rates.admit("read") == rates.admit("write") == 0
    for _ in range(10000):
        rates.admit("inference")
    assert set(rates.buckets) == {"inference", "read", "write", "public"}
    assert sum(len(b) for b in rates.buckets.values()) == 3
    clock[0] = 60
    assert rates.admit("inference") == 0


def test_rate_limit_429_and_forwarded_ip_cannot_bypass(api, row):
    # The instantiated middleware snapshots limits; make a separate app with a small budget.
    cfg = api.app.state.settings.model_copy(update={"rate_limit_inference": 1})
    with TestClient(create_app(cfg), headers={"X-RMI-Service-Key": SERVICE_KEY}) as client:
        first = client.post("/predict", json=row, headers={"X-Forwarded-For": "192.0.2.1"})
        second = client.post("/predict", json=row, headers={"X-Forwarded-For": "192.0.2.2"})
        assert first.status_code == 200 and second.status_code == 429
        assert second.headers["retry-after"] and second.json() == {
            "detail": "Request budget exhausted"
        }
        assert client.get("/model/info").status_code == 200


def test_request_size_before_json_deserialization(api):
    cfg = api.app.state.settings.model_copy(update={"request_max_bytes": 1024})
    with TestClient(create_app(cfg), headers={"X-RMI-Service-Key": SERVICE_KEY}) as client:
        for path in ("/predict", "/predict/batch"):
            response = client.post(
                path,
                content=b"not-json-private" * 100,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 413 and "private" not in response.text


def test_chunked_oversized_body_never_reaches_inner_application():
    cfg = Settings(_env_file=None, n8n_service_api_key=SERVICE_KEY, request_max_bytes=1024)
    called = []
    sent = []

    async def inner(scope, receive, send):
        called.append(True)

    chunks = iter(
        [
            {"type": "http.request", "body": b"x" * 600, "more_body": True},
            {"type": "http.request", "body": b"x" * 600, "more_body": False},
        ]
    )

    async def receive():
        return next(chunks)

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "path": "/predict/batch",
        "method": "POST",
        "headers": [(b"host", b"testserver"), (b"x-rmi-service-key", SERVICE_KEY.encode())],
    }
    asyncio.run(HttpSecurity(inner, cfg)(scope, receive, send))
    assert sent[0]["status"] == 413 and not called


def test_trusted_host_and_cors_default_restrictive(api):
    assert api.get("/health", headers={"Host": "evil.example"}).status_code == 400
    response = api.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
    assert api.get("/health", headers={"Host": "testserver:badport"}).status_code == 400


def test_configured_cors_and_browser_service_header_rejected():
    cfg = Settings(_env_file=None, cors_allowed_origins=["https://frontend.example.org"])
    with TestClient(create_app(cfg)) as client:
        headers = {
            "Origin": "https://frontend.example.org",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        allowed = client.options("/predict", headers=headers)
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://frontend.example.org"
        assert "access-control-allow-credentials" not in allowed.headers
        assert (
            client.options(
                "/predict", headers={**headers, "Origin": "https://evil.example"}
            ).status_code
            == 400
        )
        assert (
            client.options(
                "/predict",
                headers={**headers, "Access-Control-Request-Headers": "X-RMI-Service-Key"},
            ).status_code
            == 400
        )


def production_cfg():
    return Settings(
        _env_file=None,
        environment="production",
        n8n_service_api_key=SERVICE_KEY,
        allowed_hosts=["api.example.org"],
        model_artifact_path=Path.cwd() / "not-mounted-model",
        model_artifact_root=Path.cwd(),
        model_artifact_manifest_sha256="a" * 64,
        databricks_server_hostname="test.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/test",
        databricks_client_id="00000000-0000-4000-8000-000000000000",
        databricks_client_secret="synthetic-test-only",
    )


@pytest.mark.parametrize(
    "problem",
    ["missing_key", "hosts", "wildcard_cors", "no_model_pin", "database_tls", "personal_store"],
)
def test_production_fail_closed(problem):
    from pydantic import SecretStr

    cfg = production_cfg()
    if problem == "missing_key":
        cfg.n8n_service_api_key = SecretStr("")
    elif problem == "hosts":
        cfg.allowed_hosts = ["*"]
    elif problem == "wildcard_cors":
        cfg.cors_allowed_origins = ["*"]
    elif problem == "no_model_pin":
        cfg.model_artifact_manifest_sha256 = ""
    elif problem == "database_tls":
        cfg.database_url = SecretStr("postgresql://private.invalid/db")
    else:
        cfg.databricks_credential_target = "personal-store"
    with pytest.raises(RuntimeError) as caught:
        validate_deployment(cfg)
    assert "private" not in str(caught.value) and SERVICE_KEY not in str(caught.value)


def test_production_readiness_vs_liveness_and_no_docs():
    cfg = production_cfg()
    validate_deployment(cfg)
    with TestClient(create_app(cfg), base_url="https://api.example.org") as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.get("/ready").json() == {"status": "not_ready"}
        assert client.get("/docs").status_code == client.get("/openapi.json").status_code == 404


def test_security_headers_request_id_logs_and_errors_are_sanitized(api, caplog):
    caplog.set_level(logging.INFO, logger="app.core.http_security")

    async def explode():
        raise RuntimeError("private-dsn-secret-filesystem-path")

    api.app.add_api_route("/private-path-secret", explode)
    response = api.get(
        "/private-path-secret?token=private-query",
        headers={"X-Request-ID": "private-client-id", "X-RMI-Service-Key": "wrong-private"},
    )
    assert response.status_code == 500
    assert "private" not in response.text and "private" not in caplog.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-request-id"] != "private-client-id"
    assert "category=internal_error" in caplog.text


def test_openapi_declares_service_auth_without_secret_examples(api):
    schema = api.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["ServiceKey"]["name"] == "X-RMI-Service-Key"
    assert SERVICE_KEY not in json.dumps(schema)
    assert all(path in schema["paths"] for path in PROTECTED_PATHS)
