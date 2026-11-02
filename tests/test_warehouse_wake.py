import io
import json
import logging
import threading
import urllib.error
from unittest.mock import MagicMock, Mock

import pytest
from databricks.sql.exc import RequestError

from app.data.databricks_client import DataAccessError, DatabricksClient
from app.data.warehouse_wake import recover_stopped_warehouse
from tests.test_actions_scheduler import FakeClock
from tests.test_databricks_client import configured

PRIVATE = "private-secret private-host private-message"


def settings():
    return configured().model_copy(update={
        "databricks_http_path": "/sql/1.0/warehouses/0123456789abcdef",
        "databricks_warehouse_wake_enabled": True,
    })


def opener_for(values):
    responses = []
    for value in values:
        response = MagicMock()
        response.read.return_value = json.dumps(value).encode()
        response.__enter__.return_value = response
        responses.append(response)
    return Mock(open=Mock(side_effect=responses))


def recover(values, *, cancel=None):
    clock = FakeClock()
    opener = opener_for(values)
    creds = Mock(headers=Mock(return_value={"Authorization": "Bearer " + PRIVATE}))
    result = recover_stopped_warehouse(
        settings(), creds, cancel or threading.Event(), opener=opener,
        clock=clock, sleep=clock.sleep,
    )
    return result, opener, clock


def test_stopped_starts_exactly_once_then_waits_for_running(caplog):
    with caplog.at_level(logging.INFO):
        result, opener, clock = recover([
            {"state": "STOPPED"}, {}, {"state": "STARTING"}, {"state": "RUNNING"},
        ])
    assert result is True and clock.delays == [5, 5]
    requests = [call.args[0] for call in opener.open.call_args_list]
    assert [req.method for req in requests] == ["GET", "POST", "GET", "GET"]
    assert requests[1].full_url.endswith("/0123456789abcdef/start")
    assert requests[1].data == b"{}"
    assert "stage=start_requested" in caplog.text and "stage=running" in caplog.text
    assert PRIVATE not in caplog.text


def test_already_starting_never_starts_again():
    result, opener, _ = recover([{"state": "STARTING"}, {"state": "RUNNING"}])
    assert result is True
    assert all(call.args[0].method == "GET" for call in opener.open.call_args_list)


@pytest.mark.parametrize("state", ["RUNNING", "STOPPING", "DELETED", "unknown"])
def test_other_states_never_trigger_start(state):
    result, opener, _ = recover([{"state": state}])
    assert result is False and opener.open.call_count == 1


def test_wake_budget_exhaustion_still_fails_without_additional_starts():
    clock, opener = FakeClock(), opener_for([{"state": "STARTING"}] * 20)
    with pytest.raises(TimeoutError):
        recover_stopped_warehouse(
            settings(), Mock(headers=Mock(return_value={})), threading.Event(),
            opener=opener, clock=clock, sleep=clock.sleep,
        )
    assert clock.now <= 60
    assert all(call.args[0].method == "GET" for call in opener.open.call_args_list)


@pytest.mark.parametrize("status", [400, 401, 403, 429, 503, 504])
def test_control_plane_rejection_is_not_retried_or_suppressed(status):
    opener = Mock()
    opener.open.side_effect = urllib.error.HTTPError(
        "https://private.invalid", status, PRIVATE, {}, io.BytesIO(b"{}"),
    )
    with pytest.raises(urllib.error.HTTPError):
        recover_stopped_warehouse(
            settings(), Mock(headers=Mock(return_value={})), threading.Event(), opener=opener,
        )
    assert opener.open.call_count == 1


def test_cancelled_operation_cannot_wake_compute():
    cancel = threading.Event()
    cancel.set()
    opener = Mock()
    with pytest.raises(TimeoutError):
        recover_stopped_warehouse(settings(), Mock(), cancel, opener=opener)
    opener.open.assert_not_called()


@pytest.mark.parametrize("path", ["/fixture", "/sql/1.0/warehouses/../other", "https://private"])
def test_invalid_paths_cannot_reach_control_plane(path):
    cfg = settings().model_copy(update={"databricks_http_path": path})
    opener = Mock()
    assert recover_stopped_warehouse(cfg, Mock(), threading.Event(), opener=opener) is False
    opener.open.assert_not_called()


def successful_connection():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("probe",)]
    cursor.fetchone.return_value = (configured().databricks_client_id,)
    cursor.fetchmany.side_effect = [[(1,)], []]
    return connection


def test_failed_open_session_recovers_under_same_query_path(monkeypatch):
    error = RequestError(PRIVATE, {"http-code": 400, "method": "OpenSession"})
    connect = Mock(side_effect=[error, successful_connection()])
    wake = Mock(return_value=True)
    monkeypatch.setattr("app.data.databricks_client.recover_stopped_warehouse", wake)
    frame = DatabricksClient(settings(), connect).select("SELECT 1 AS probe", max_rows=1)
    assert len(frame) == 1 and connect.call_count == 2
    wake.assert_called_once()


@pytest.mark.parametrize("status,method,enabled", [
    (401, "OpenSession", True), (403, "OpenSession", True),
    (503, "OpenSession", True), (504, "OpenSession", True),
    (400, "ExecuteStatement", True), (400, "OpenSession", False),
])
def test_no_wake_for_unrelated_failures_or_disabled_option(monkeypatch, status, method, enabled):
    connect = Mock(side_effect=RequestError(PRIVATE, {"http-code": status, "method": method}))
    wake = Mock()
    monkeypatch.setattr("app.data.databricks_client.recover_stopped_warehouse", wake)
    cfg = settings().model_copy(update={"databricks_warehouse_wake_enabled": enabled})
    with pytest.raises(DataAccessError):
        DatabricksClient(cfg, connect).select("SELECT 1", max_rows=1)
    assert connect.call_count == 1
    wake.assert_not_called()


def test_second_open_failure_cannot_repeat_wake(monkeypatch):
    error = RequestError(PRIVATE, {"http-code": 400, "method": "OpenSession"})
    connect, wake = Mock(side_effect=[error, error]), Mock(return_value=True)
    monkeypatch.setattr("app.data.databricks_client.recover_stopped_warehouse", wake)
    with pytest.raises(DataAccessError):
        DatabricksClient(settings(), connect).select("SELECT 1", max_rows=1)
    assert connect.call_count == 2
    wake.assert_called_once()


def test_normal_select_never_calls_control_plane_even_when_enabled(monkeypatch):
    connect, wake = Mock(return_value=successful_connection()), Mock()
    monkeypatch.setattr("app.data.databricks_client.recover_stopped_warehouse", wake)
    assert len(DatabricksClient(settings(), connect).select("SELECT 1", max_rows=1)) == 1
    connect.assert_called_once()
    wake.assert_not_called()


def test_no_reconnect_when_warehouse_cannot_be_recovered(monkeypatch):
    error = RequestError(PRIVATE, {"http-code": 400, "method": "OpenSession"})
    connect, wake = Mock(side_effect=error), Mock(return_value=False)
    monkeypatch.setattr("app.data.databricks_client.recover_stopped_warehouse", wake)
    with pytest.raises(DataAccessError):
        DatabricksClient(settings(), connect).select("SELECT 1", max_rows=1)
    connect.assert_called_once()
    wake.assert_called_once()
