import io
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.persist_current_predictions import (
    MAX_RESPONSE,
    Client,
    OrchestrationError,
    safe_category,
    safe_path,
    safe_stage,
    safe_status,
)


def test_safe_stage_rejects_unknown():
    assert safe_stage("not-a-stage") == "internal"
    assert safe_stage("persistence") == "persistence"


def test_safe_category_rejects_unknown():
    assert safe_category("totally-unknown", 500) == "server_error"


def test_orchestration_error_preserves_original_category():
    exc = OrchestrationError("persistence", status=503, category="server_unavailable_or_timeout")
    assert exc.stage == "persistence"
    assert exc.status == 503
    assert exc.category == "server_unavailable_or_timeout"


@pytest.mark.parametrize("value", [None, [], {}, "SECRET", True, -1, 999])
def test_diagnostic_inputs_cannot_leak_or_break_classification(value):
    assert safe_path(value) is None
    assert safe_status(value) == 0
    assert safe_category(value, 503) == "server_unavailable_or_timeout"


def response_client(body, *, length=None):
    response = Mock()
    response.status = 200
    response.headers = {} if length is None else {"Content-Length": str(length)}
    response.read1.side_effect = io.BytesIO(body).read1
    response.fp = SimpleNamespace(raw=SimpleNamespace(_sock=Mock()))
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    return Client("https://api.example.org", "x" * 32, opener=opener)


@pytest.mark.parametrize(
    ("body", "length", "category"),
    [
        (b"{}", MAX_RESPONSE + 1, "response_too_large"),
        (b"{}", 5, "truncated_response"),
        (b"[]", None, "invalid_json_shape"),
    ],
)
def test_request_preserves_specific_response_failure(body, length, category):
    with pytest.raises(OrchestrationError) as failure:
        response_client(body, length=length).request("/ready")
    assert failure.value.stage == "response"
    assert failure.value.path == "/ready"
    assert failure.value.status == 200
    assert failure.value.category == category


def test_main_emits_only_allowlisted_diagnostics(monkeypatch, capsys):
    from scripts import persist_current_predictions as module

    error = OrchestrationError(
        "persistence",
        path="https://private.example/SECRET",
        status=503,
        category="server_unavailable_or_timeout",
    )
    monkeypatch.setattr(module, "Client", Mock(return_value=Mock(run=Mock(side_effect=error))))
    with pytest.raises(SystemExit, match="failed: persistence"):
        module.main()
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "stage": "persistence",
        "status": 503,
        "category": "server_unavailable_or_timeout",
    }
    assert "SECRET" not in output.err


def test_warm_exhaustion_preserves_last_http_status():
    client = response_client(b"{}")
    client.request = Mock(return_value=(503, None))
    client.sleep = Mock()
    with pytest.raises(OrchestrationError) as failure:
        client.warm("/ready", lambda _: False, "ready")
    assert failure.value.status == 503
    assert client.last_failure["status"] == 503
