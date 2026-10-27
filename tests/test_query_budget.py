import threading
import time
import uuid
from unittest.mock import MagicMock

import pytest

from app.data.databricks_client import DataAccessError, DatabricksClient
from app.data.query_budget import QueryCapacityExceeded, QueryDeadlineExceeded, execute_bounded
from tests.test_workload_auth import config


def test_deadline_requests_cancel_and_keeps_capacity_until_cleanup():
    key = (str(uuid.uuid4()), "fixture")
    entered, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    cursor = MagicMock()
    cursor.cancel.side_effect = cancelled.set

    def blocking(stop, attach):
        attach(cursor)
        entered.set()
        release.wait(2)
        assert stop.is_set()

    start = time.monotonic()
    try:
        with pytest.raises(QueryDeadlineExceeded):
            execute_bounded(key, 1, 0, 0.06, blocking)
        assert time.monotonic() - start < 0.8
        assert entered.is_set() and cancelled.wait(1)
        with pytest.raises(QueryCapacityExceeded):
            execute_bounded(key, 1, 0, 0.5, lambda *args: None)
    finally:
        release.set()


def test_timeout_during_connect_never_starts_sql():
    release, closed = threading.Event(), threading.Event()
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    connection.close.side_effect = closed.set

    def connect(**kwargs):
        release.wait(2)
        return connection

    settings = config(
        databricks_query_timeout_seconds=0.06,
        databricks_server_hostname="connect-timeout.cloud.databricks.com",
    )
    try:
        with pytest.raises(DataAccessError, match="deadline"):
            DatabricksClient(settings, connect).select("SELECT 1", max_rows=1)
    finally:
        release.set()
    assert closed.wait(1)
    cursor.execute.assert_not_called()


def test_reserved_budget_parameter_rejected_before_connection():
    connect = MagicMock()
    with pytest.raises(ValueError, match="Reserved"):
        DatabricksClient(config(), connect).select("SELECT 1", {"__rmi_row_limit": 999}, max_rows=1)
    connect.assert_not_called()


def test_inconsistent_concurrency_cannot_bypass_gate():
    key = (str(uuid.uuid4()), "fixture")
    assert execute_bounded(key, 1, 0, 1, lambda *args: 42) == 42
    with pytest.raises(QueryCapacityExceeded):
        execute_bounded(key, 2, 0, 1, lambda *args: 43)
