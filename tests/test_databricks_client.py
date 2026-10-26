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
        databricks_server_hostname="fixture.invalid",
        databricks_http_path="/fixture",
        databricks_token="fixture-only",
    )


def test_select_parameters_and_cleanup():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("value",)]
    cursor.fetchmany.side_effect = [[(1,), (2,)], []]
    connect = MagicMock(return_value=connection)
    result = DatabricksClient(configured(), connect).select(
        "SELECT :v AS value", {"v": 1}, max_rows=2
    )
    assert result.value.tolist() == [1, 2]
    cursor.execute.assert_called_once_with("SELECT :v AS value", parameters={"v": 1})
    connection.close.assert_called_once()
    cursor.close.assert_called_once()
    assert connect.call_args.kwargs["use_inline_params"] is False


def test_budget_rejects_partial_export_and_closes():
    connection, cursor = MagicMock(), MagicMock()
    connection.cursor.return_value = cursor
    cursor.description = [("value",)]
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
