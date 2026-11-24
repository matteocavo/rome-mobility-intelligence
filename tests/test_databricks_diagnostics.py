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


@pytest.mark.parametrize("operation", ["session_open", "warehouse_start"])
def test_http400_structured_details_are_bounded_and_body_read_once(caplog, operation):
    from uuid import UUID

    upstream_id = "12345678-1234-1234-1234-123456789abc"
    stream = Mock(wraps=io.BytesIO(json.dumps({
        "error_code": "BAD_REQUEST",
        "message": "Cannot start warehouse because workspace is suspended",
        "request_id": upstream_id,
        "private_extra": PRIVATE,
    }).encode()))
    error = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE, {}, stream)
    assert failure_error_code(error) == "BAD_REQUEST"
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger(__name__), error, operation, 1)
    details = [json.loads(r.message.split(" ", 1)[1]) for r in caplog.records
               if r.message.startswith("databricks_http400_detail ")]
    assert len(details) == 1
    detail = details[0]
    assert detail["operation"] == operation and detail["http_status"] == 400
    assert detail["error_code"] == "BAD_REQUEST"
    assert detail["message"] == "Cannot start warehouse because workspace is suspended"
    assert detail["databricks_request_id"] == upstream_id
    UUID(detail["local_correlation_id"])
    stream.read.assert_called_once_with(4097)
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("secret", [
    "Authorization: Bearer abc123secret",
    "password=superSecretValue", "client_secret=clientSecretValue",
    "https://private.example/object?X-Amz-Signature=secretValue",
    "jdbc:spark://private.example;UID=alice;PWD=hidden",
    "postgresql://alice:secret@private.example/db",
    "alice@example.com", "AliceSmith", "dapi123456789abcdef",
    '"private secret value"', "Bearer abc123secret", "Basic abc123secret",
    "\r\nFORGED_EVENT=privateValue", "C:\\Users\\AliceSmith\\private.txt",
])
def test_message_projection_excludes_credentials_and_identifiers(secret):
    from app.core.databricks_diagnostics import sanitized_message

    text = sanitized_message("Cannot start warehouse " + secret)
    assert "Cannot start warehouse" in text
    assert "[redacted]" in text
    for prohibited in ["abc123secret", "superSecretValue", "clientSecretValue", "secretValue",
                       "private.example", "alice@example.com", "AliceSmith", "dapi123456789abcdef",
                       "FORGED_EVENT", "privateValue", "private.txt"]:
        assert prohibited not in text
    assert "\n" not in text and "\r" not in text
    assert len(text) <= 512


def test_connector_details_use_only_own_context_not_implicit_exception(caplog):
    error = RequestError(PRIVATE, {"http-code": 400, "method": "OpenSession",
                                  "error-message": "Invalid access token scope",
                                  "request-id": "a" * 32})
    error.__context__ = RuntimeError("password=privateValue")
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger(__name__), error, "session_open", 1)
    assert '"message": "Invalid access token scope"' in caplog.text
    assert '"databricks_request_id": "' + "a" * 32 in caplog.text
    assert PRIVATE not in caplog.text and "privateValue" not in caplog.text


@pytest.mark.parametrize("body", [b"bad json", b"[]", b"x" * 4097])
def test_missing_details_fail_closed_and_do_not_replace_original_error(caplog, body):
    error = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE,
                                  {"X-Request-Id": "Bearer privateValue"}, io.BytesIO(body))
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger(__name__), error, "warehouse_start", 1)
    assert '"message": "unavailable"' in caplog.text
    assert '"databricks_request_id": "unavailable"' in caplog.text
    assert PRIVATE not in caplog.text and "privateValue" not in caplog.text


def test_http_header_request_id_and_json_cannot_inject_log(caplog):
    error = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE,
                                  {"X-Databricks-Request-Id": "b" * 32},
                                  io.BytesIO(json.dumps(
                                      {"message": "Invalid request\npassword=secret"}
                                  ).encode()))
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger(__name__), error, "warehouse_start", 1)
    detail = json.loads(next(r.message.split(" ", 1)[1] for r in caplog.records
                             if r.message.startswith("databricks_http400_detail ")))
    assert detail["databricks_request_id"] == "b" * 32
    assert "secret" not in detail["message"] and "\n" not in detail["message"]


@pytest.mark.parametrize("operation,status", [("select", 400), ("warehouse_get", 400),
                                               ("warehouse_start", 503), ("session_open", 403)])
def test_new_detail_log_is_limited_to_requested_400_operations(caplog, operation, status):
    error = urllib.error.HTTPError(
        "https://private.invalid", status, PRIVATE, {}, io.BytesIO(b"{}")
    )
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger(__name__), error, operation, 1)
    assert "databricks_http400_detail " not in caplog.text



def test_broken_optional_headers_do_not_change_failure_handling(caplog):
    headers = Mock()
    headers.get.side_effect = RuntimeError("private optional header failure")
    error = urllib.error.HTTPError("https://private.invalid", 400, PRIVATE, headers,
                                  io.BytesIO(b'{"error_code":"BAD_REQUEST"}'))
    with caplog.at_level(logging.WARNING):
        log_failure(logging.getLogger(__name__), error, "warehouse_start", 1)
    assert failure_error_code(error) == "BAD_REQUEST"
    assert '"message": "unavailable"' in caplog.text
    assert "private optional" not in caplog.text


# --- Databricks Free daily quota classification (simulated errors only) ---
from app.core.databricks_diagnostics import is_daily_quota_exhausted  # noqa: E402
from app.data.databricks_client import DataQuotaExhaustedError  # noqa: E402

QUOTA_TEXT = "Your workspace reached the free daily limit of compute"


def quota_http(code=400, error_code="BAD_REQUEST", text=QUOTA_TEXT):
    return urllib.error.HTTPError(
        "https://private.invalid", code, PRIVATE, {},
        io.BytesIO(json.dumps({"error_code": error_code, "message": text}).encode()),
    )


def quota_open_session(text="Free daily limit", code=400):
    return RequestError(PRIVATE, {"http-code": code, "method": "OpenSession",
                                  "error-message": text})


def classified(error):
    log_failure(logging.getLogger("t"), error, "select", 1)
    return is_daily_quota_exhausted(error)


def test_quota_open_session_request_error_is_recognized():
    assert classified(quota_open_session())


def test_quota_http_warehouse_start_rejection_is_recognized():
    assert classified(quota_http())


def test_quota_found_through_nested_original_exception():
    outer = RequestError(PRIVATE, {"original-exception": quota_http()})
    assert classified(outer)


@pytest.mark.parametrize("error", [
    quota_open_session("Invalid parameter"),
    quota_open_session("Free daily limit", code=503),
    quota_open_session("Free daily limit", code=504),
    quota_open_session("Free daily limit", code=429),
    quota_http(error_code="INVALID_PARAMETER_VALUE"),
    quota_http(text="Rate limit for free tier reached"),
    quota_http(text="daily free limit"),
    quota_http(text="limit daily free"),
    quota_http(code=503),
    quota_http(code=504),
    RuntimeError(QUOTA_TEXT),
    RequestError(QUOTA_TEXT, {"http-code": 400, "method": "ExecuteStatement"}),
    TimeoutError(QUOTA_TEXT),
])
def test_non_specific_signals_are_not_quota(error):
    assert not classified(error)


def test_quota_message_is_never_in_the_raised_exception_or_logs(caplog):
    connect = Mock(side_effect=quota_open_session())
    with caplog.at_level(logging.WARNING), pytest.raises(DataQuotaExhaustedError) as caught:
        DatabricksClient(configured(), connect).select("SELECT 1", max_rows=1)
    text = caplog.text + str(caught.value)
    assert "databricks_daily_quota_exhausted" in text
    assert PRIVATE not in text and "fixture.cloud.databricks.com" not in text
    assert caught.value.__cause__ is None


def test_other_400_remains_generic_data_access_error():
    connect = Mock(side_effect=quota_open_session("Invalid parameter"))
    with pytest.raises(DataAccessError) as caught:
        DatabricksClient(configured(), connect).select("SELECT 1", max_rows=1)
    assert not isinstance(caught.value, DataQuotaExhaustedError)
