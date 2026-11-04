import io
import json
import logging
import urllib.error
from unittest.mock import Mock

import pytest
from databricks.sql.exc import ProgrammingError, RequestError

from app.core.config import Settings
from app.core.databricks_diagnostics import (
    failure_category,
    failure_error_code,
    failure_metadata,
    log_failure,
)
from app.core.workload_auth import WorkloadAuthenticationError, exchange_token
from app.data.databricks_client import DataAccessError, DatabricksClient
from app.services.batch_scoring import BatchScoringService
from tests.test_databricks_client import configured

PRIVATE = "private-token private-host private-query"


def test_scoring_failure_never_calls_history_insert():
    scoring, history = Mock(), Mock()
    scoring.score.side_effect = DataAccessError(PRIVATE)
    settings = Settings(_env_file=None, enable_prediction_persistence=True)
    with pytest.raises(DataAccessError):
        BatchScoringService(scoring, history, settings).run(2)
    history.insert_batch.assert_not_called()


@pytest.mark.parametrize("error,category", [
    (RequestError(PRIVATE, {"http-code": 401}), "databricks_authentication"),
    (RequestError(PRIVATE, {"http-code": 403}), "databricks_authorization"),
    (RequestError(PRIVATE, {"http-code": 503}), "databricks_compute_unavailable"),
    (RequestError(PRIVATE, {"http-code": 504}), "databricks_timeout"),
    (RequestError(PRIVATE, {"http-code": 400, "error-message": "Free daily limit"}),
     "databricks_compute_unavailable"),
    (TimeoutError(PRIVATE), "databricks_timeout"),
    (urllib.error.URLError(PRIVATE), "databricks_connectivity"),
    (ProgrammingError(PRIVATE), "databricks_query_error"),
    (RuntimeError(PRIVATE), "databricks_unknown"),
])
def test_failure_categories_do_not_export_messages(error, category):
    assert failure_category(error) == category


def test_nested_oauth_category_survives_connector_wrapper():
    error = RequestError(PRIVATE, {"original-exception": WorkloadAuthenticationError(
        PRIVATE, "databricks_authentication"
    )})
    assert failure_category(error) == "databricks_authentication"


def test_connection_failure_log_and_exception_are_sanitized(caplog):
    connect = Mock(side_effect=RequestError(PRIVATE, {"http-code": 403}))
    with caplog.at_level(logging.WARNING), pytest.raises(DataAccessError) as caught:
        DatabricksClient(configured(), connect).select("SELECT 1", max_rows=1)
    assert "databricks_authorization" in caplog.text
    assert PRIVATE not in caplog.text + str(caught.value)
    assert "fixture.cloud.databricks.com" not in caplog.text


def test_open_session_bad_request_has_http_category_and_safe_metadata(caplog):
    error = RequestError(PRIVATE, {
        "http-code": 400, "method": "OpenSession", "error-message": PRIVATE,
        "session-id": PRIVATE, "query-id": PRIVATE,
    })
    assert failure_category(error) == "databricks_http_error"
    with caplog.at_level(logging.WARNING), pytest.raises(DataAccessError):
        DatabricksClient(configured(), Mock(side_effect=error)).select("SELECT 1", max_rows=1)
    assert "http_status=400 rpc=open_session" in caplog.text
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("value", [PRIVATE, {}, [], True, None, 999])
def test_metadata_rejects_untrusted_values(value):
    error = RequestError(PRIVATE, {"http-code": value, "method": value})
    assert failure_metadata(error) == (0, "unknown")


def test_metadata_walks_bounded_nested_context_and_cycles():
    inner = RequestError(PRIVATE, {"http-code": 503, "method": "ExecuteStatement"})
    outer = RequestError(PRIVATE, {"original-exception": inner})
    inner.__cause__ = outer
    assert failure_metadata(outer) == (503, "execute_statement")


@pytest.mark.parametrize("status,category", [
    (401, "databricks_authentication"), (403, "databricks_authorization"),
])
def test_oauth_status_is_preserved_without_secret_output(monkeypatch, caplog, status, category):
    opener = Mock()
    opener.open.side_effect = urllib.error.HTTPError(
        "https://private.invalid", status, PRIVATE, {}, None
    )
    monkeypatch.setattr("app.core.workload_auth.urllib.request.build_opener", lambda *a: opener)
    with caplog.at_level(logging.WARNING), pytest.raises(WorkloadAuthenticationError) as caught:
        exchange_token("fixture.cloud.databricks.com", "fixture-id", PRIVATE)
    assert caught.value.category == category
    assert category in caplog.text
    assert PRIVATE not in caplog.text + str(caught.value)


def test_http_rejection_is_not_a_network_failure_or_inherited_session_context():
    initial = RequestError(PRIVATE, {"http-code": 400, "method": "OpenSession"})
    rejection = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE, {}, None)
    rejection.__context__ = initial
    rejection.__cause__ = initial
    assert failure_category(rejection) == "databricks_http_error"
    assert failure_metadata(rejection) == (400, "unknown")
    assert failure_category(urllib.error.URLError(PRIVATE)) == "databricks_connectivity"
    assert failure_category(urllib.error.URLError(TimeoutError(PRIVATE))) == "databricks_timeout"


@pytest.mark.parametrize("code", ["INVALID_PARAMETER_VALUE", "PERMISSION_DENIED",
                                  "RESOURCE_EXHAUSTED"])
def test_http_and_connector_error_codes_are_allowlisted_and_body_is_read_once(code):
    stream = Mock(wraps=io.BytesIO(json.dumps({"error_code": code, "message": PRIVATE}).encode()))
    error = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE, {}, stream)
    assert failure_error_code(error) == code
    assert failure_error_code(error) == code
    stream.read.assert_called_once_with(4097)
    assert failure_error_code(RequestError(PRIVATE, {"error-code": code})) == code


@pytest.mark.parametrize("code", [PRIVATE, "BAD_REQUEST\n" + PRIVATE, {}, [], True, None, 400])
def test_unknown_or_malformed_error_codes_are_never_retained(code):
    error = urllib.error.HTTPError(
        "https://private.invalid", 400, PRIVATE, {},
        io.BytesIO(json.dumps({"error_code": code, "message": PRIVATE}).encode()),
    )
    assert failure_error_code(error) == "unknown"
    assert failure_error_code(RequestError(PRIVATE, {"error_code": code})) == "unknown"


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"x" * 4097])
def test_invalid_or_oversized_rejection_body_is_discarded(body):
    error = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE, {}, io.BytesIO(body))
    assert failure_error_code(error) == "unknown"


@pytest.mark.parametrize("code,category", [
    ("RESOURCE_EXHAUSTED", "databricks_compute_unavailable"),
    ("UNAUTHENTICATED", "databricks_authentication"),
    ("PERMISSION_DENIED", "databricks_authorization"),
    ("INVALID_PARAMETER_VALUE", "databricks_http_error"),
])
def test_rejection_category_uses_only_recognized_error_codes(code, category):
    error = urllib.error.HTTPError(
        "https://private.invalid", 400, PRIVATE, {},
        io.BytesIO(json.dumps({"error_code": code}).encode()),
    )
    assert failure_category(error) == category


def test_metadata_never_fills_missing_fields_from_an_earlier_request():
    initial = RequestError(PRIVATE, {"http-code": 400, "method": "OpenSession"})
    recovery = RequestError(PRIVATE, {"http-code": 503, "original-exception": initial})
    assert failure_metadata(recovery) == (503, "unknown")
    wrapper = RuntimeError(PRIVATE)
    wrapper.__context__ = initial
    assert failure_metadata(wrapper) == (0, "unknown")
    malformed_http = urllib.error.HTTPError("https://private.invalid", None, PRIVATE, {}, None)
    malformed_http.__cause__ = initial
    assert failure_metadata(malformed_http) == (0, "unknown")


def test_sql_query_error_keeps_its_category_even_with_http_400():
    error = RequestError(PRIVATE, {"http-code": 400, "sql-state": "42000"})
    assert failure_category(error) == "databricks_query_error"


def test_diagnostic_fields_and_unreadable_body_fail_closed(caplog):
    stream = Mock()
    stream.read.side_effect = RuntimeError(PRIVATE)
    error = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE, {}, stream)
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger(__name__), error, PRIVATE, 12, warehouse_state=PRIVATE)
    assert "operation=unknown" in caplog.text
    assert "warehouse_state=unknown" in caplog.text
    assert "http_status=400 rpc=unknown error_code=unknown" in caplog.text
    assert PRIVATE not in caplog.text
    assert "private.invalid" not in caplog.text
