import logging
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.data.databricks_client import (
    DataAccessError,
    DatabricksClient,
    ExportBudgetError,
    guard_select,
    table_name,
)


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO t VALUES (1)",
        "DELETE FROM t",
        "UPDATE t SET x=1",
        "DROP TABLE t",
        "CREATE TABLE t(x INT)",
        "ALTER TABLE t ADD x INT",
        "MERGE INTO t USING u ON true",
        "SELECT 1; DELETE FROM t",
        "WITH d AS (DELETE FROM t) SELECT 1",
        "SELECT 1 INTO t",
    ],
)
def test_readonly_guard_rejects_writes(query):
    with pytest.raises(ValueError):
        guard_select(query)


def test_select_strings_and_parameters_allowed():
    guard_select("SELECT 'DELETE; UPDATE' AS harmless WHERE 1=:value")


def configured():
    return Settings(
        _env_file=None,
        databricks_server_hostname="fixture.cloud.databricks.com",
        databricks_http_path="/fixture",
        databricks_client_id="11111111-1111-4111-8111-111111111111",
        databricks_client_secret="fixture-only",
    )


def test_select_parameters_and_cleanup():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("value",)]
    cursor.fetchone.return_value = (configured().databricks_client_id,)
    cursor.fetchmany.side_effect = [[(1,), (2,)], []]
    connect = MagicMock(return_value=connection)
    result = DatabricksClient(configured(), connect).select(
        "SELECT :v AS value", {"v": 1}, max_rows=2
    )
    assert result.value.tolist() == [1, 2]
    query_call = cursor.execute.call_args
    assert "LIMIT :__rmi_row_limit" in query_call.args[0]
    assert query_call.kwargs["parameters"] == {"v": 1, "__rmi_row_limit": 3}
    assert connect.call_args.kwargs["session_configuration"]["STATEMENT_TIMEOUT"] == "120"
    assert "access_token" not in connect.call_args.kwargs
    connection.close.assert_called_once()
    cursor.close.assert_called_once()
    assert connect.call_args.kwargs["use_inline_params"] is False
    assert connect.call_args.kwargs["use_cloud_fetch"] is True


def test_select_timing_log_has_only_safe_stages_and_aggregate_data(caplog):
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("value",)]
    cursor.fetchone.return_value = (configured().databricks_client_id,)
    cursor.fetchmany.side_effect = [[(1,)], []]

    with caplog.at_level(logging.INFO, logger="app.data.databricks_client"):
        DatabricksClient(configured(), lambda **kwargs: connection).select(
            "SELECT 1 AS value", max_rows=1
        )

    record = next(
        record for record in caplog.records if "databricks_select_timing" in record.message
    )
    for stage in (
        "connection_auth_ms=",
        "identity_check_ms=",
        "sql_execute_ms=",
        "first_batch_ms=",
        "fetch_transfer_ms=",
        "fetch_complete_ms=",
        "dataframe_conversion_ms=",
        "rows=1",
        "dataframe_bytes=",
    ):
        assert stage in record.message
    assert "fixture-only" not in record.message


def test_budget_rejects_partial_export_and_closes():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("value",)]
    cursor.fetchone.return_value = (configured().databricks_client_id,)
    cursor.fetchmany.return_value = [(1,), (2,)]
    with pytest.raises(ExportBudgetError):
        DatabricksClient(configured(), lambda **kw: connection).select("SELECT 1", max_rows=1)
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_connector_error_does_not_expose_secret():
    connection = MagicMock()
    connection.cursor.side_effect = RuntimeError("sensitive token")
    with pytest.raises(DataAccessError) as error:
        DatabricksClient(configured(), lambda **kw: connection).select("SELECT 1", max_rows=1)
    assert "sensitive" not in str(error.value)
    connection.close.assert_called_once()


def test_identifier_injection():
    with pytest.raises(ValueError):
        table_name(configured(), "table; DROP TABLE t")


def test_compact_public_fetch_preserves_changed_categories_and_nulls():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("lineage",), ("value",)]
    cursor.fetchone.return_value = (configured().databricks_client_id,)
    cursor.fetchmany.side_effect = [[("A", 1), (None, 2)], [("B", 3)], []]
    result = DatabricksClient(configured(), lambda **kw: connection).select(
        "SELECT lineage, value FROM t", max_rows=3, compact_strings=True
    )
    assert result.value.tolist() == [1, 2, 3]
    assert cursor.arraysize == 1000
    assert result.lineage.iloc[0] == "A" and result.lineage.iloc[2] == "B"
    assert result.lineage.isna().tolist() == [False, True, False]


def test_compaction_never_weakens_original_export_memory_budget():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("lineage",)]
    cursor.fetchone.return_value = (configured().databricks_client_id,)
    cursor.fetchmany.side_effect = [[("X" * 1000,)] * 10, []]
    with pytest.raises(ExportBudgetError):
        DatabricksClient(configured(), lambda **kw: connection).select(
            "SELECT lineage FROM t", max_rows=10, max_bytes=5000, compact_strings=True
        )
    cursor.cancel.assert_called()
    cursor.close.assert_called_once()
