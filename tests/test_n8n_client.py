import inspect
import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, Mock

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.n8n_client import N8nClient, N8nTimeout, N8nUnavailable, NoRedirect


@pytest.fixture
def config():
    return Settings(
        _env_file=None,
        n8n_webhook_url="https://test-workspace.app.n8n.cloud/webhook/rmi-orchestration",
        n8n_webhook_allowed_host="test-workspace.app.n8n.cloud",
        n8n_webhook_secret="S" * 48,
    )


def response(opener, body=b'{"accepted":true}', status=202):
    entered = opener.open.return_value.__enter__.return_value
    entered.status = status
    entered.read.return_value = body


def test_unconfigured_fails_closed_without_network():
    opener = Mock()
    with pytest.raises(N8nUnavailable):
        N8nClient(Settings(_env_file=None), opener=opener).notify_prediction_orchestration()
    opener.open.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "http://test-workspace.app.n8n.cloud/webhook/x",
        "https://untrusted.example/webhook/x",
        "https://other.app.n8n.cloud/webhook/x",
        "https://test-workspace.app.n8n.cloud.evil.example/webhook/x",
        "https://user:password@test-workspace.app.n8n.cloud/webhook/x",
        "https://test-workspace.app.n8n.cloud:444/webhook/x",
        "https://test-workspace.app.n8n.cloud/api/v1/workflows",
        "https://test-workspace.app.n8n.cloud/webhook/x?secret=private",
        "https://test-workspace.app.n8n.cloud/webhook/x#fragment",
        "https://test-workspace.app.n8n.cloud/\twebhook/x",
        "http://127.0.0.1:8000/webhook/x",
    ],
)
def test_url_scheme_host_path_and_admin_api_rejected(config, url):
    config.n8n_webhook_url = SecretStr(url)
    opener = Mock()
    with pytest.raises(N8nUnavailable) as caught:
        N8nClient(config, opener=opener).notify_prediction_orchestration()
    assert url not in str(caught.value) and "password" not in str(caught.value)
    opener.open.assert_not_called()


def test_secret_header_and_only_server_generated_minimal_payload(config):
    opener = MagicMock()
    response(opener)
    result = N8nClient(config, opener=opener).notify_prediction_orchestration()
    assert result.accepted and result.request_id
    request = opener.open.call_args.args[0]
    assert request.get_header("X-rmi-orchestration-key") == "S" * 48
    assert request.method == "POST"
    payload = json.loads(request.data)
    assert set(payload) == {"event", "request_id", "generated_at"}
    assert payload["event"] == "prediction_orchestration_requested"
    assert payload["request_id"] == str(result.request_id)
    assert opener.open.call_args.kwargs["timeout"] == 5
    assert "S" * 48 not in repr(config)


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("private-url-secret"),
        urllib.error.URLError(TimeoutError("private-url-secret")),
        urllib.error.URLError("private-url-secret"),
        urllib.error.HTTPError("https://private-host/webhook/private", 302, "private", {}, None),
    ],
)
def test_timeouts_and_errors_are_sanitized(config, error, caplog):
    opener = Mock()
    opener.open.side_effect = error
    with pytest.raises(N8nUnavailable) as caught:
        N8nClient(config, opener=opener).notify_prediction_orchestration()
    assert "private" not in str(caught.value) and "S" * 48 not in str(caught.value)
    assert "private" not in caplog.text and "S" * 48 not in caplog.text
    if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError):
        assert isinstance(caught.value, N8nTimeout)
    assert opener.open.call_count == 1


@pytest.mark.parametrize(
    "body,status",
    [
        (b'{"accepted":true}', 200),
        (b'{"accepted":1}', 202),
        (b'{"accepted":true,"extra":"private"}', 202),
        (b"private non-JSON", 202),
        (b"x" * 65537, 202),
    ],
    ids=["wrong-status", "boolean-type", "extra-key", "invalid-json", "oversized"],
)
def test_only_bounded_expected_acknowledgement_is_accepted(config, body, status):
    opener = MagicMock()
    response(opener, body, status)
    with pytest.raises(N8nUnavailable) as caught:
        N8nClient(config, opener=opener).notify_prediction_orchestration()
    assert "private" not in str(caught.value)


def test_no_arbitrary_url_or_payload_surface(config):
    method = N8nClient(config).notify_prediction_orchestration
    assert not inspect.signature(method).parameters
    with pytest.raises(TypeError):
        method(url="https://evil.example")


def test_default_transport_disables_redirects_proxies_and_uses_tls(config, monkeypatch):
    opener = MagicMock()
    response(opener)
    factory = Mock(return_value=opener)
    monkeypatch.setattr("urllib.request.build_opener", factory)
    N8nClient(config).notify_prediction_orchestration()
    handlers = factory.call_args.args
    assert any(isinstance(h, NoRedirect) for h in handlers)
    assert any(isinstance(h, urllib.request.ProxyHandler) and h.proxies == {} for h in handlers)
    assert (
        NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.example")
        is None
    )


def test_loopback_allowed_only_in_explicit_test_environment(config):
    config.n8n_webhook_url = SecretStr("http://127.0.0.1:8000/webhook-test/rmi-orchestration")
    config.environment = "test"
    opener = MagicMock()
    response(opener)
    assert N8nClient(config, opener=opener).notify_prediction_orchestration().accepted


def test_weak_or_missing_secret_never_calls_webhook(config):
    config.n8n_webhook_secret = SecretStr("")
    opener = Mock()
    with pytest.raises(N8nUnavailable):
        N8nClient(config, opener=opener).notify_prediction_orchestration()
    opener.open.assert_not_called()


def test_webhook_settings_never_exposed_in_public_metadata(config):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(config)) as client:
        for path in ("/ready", "/model/info", "/openapi.json"):
            text = client.get(path).text
            assert config.n8n_webhook_url.get_secret_value() not in text
            assert config.n8n_webhook_secret.get_secret_value() not in text
            assert "n8n_webhook" not in text.lower()
