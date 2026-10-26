"""Bounded SELECT transport. Workspace least-privilege grants remain required."""

import math
import re
from contextlib import closing
from typing import Any

import pandas as pd
import sqlglot
from sqlglot import exp

from app.core.config import Settings
from app.core.workload_auth import WorkloadAuthenticationError, WorkloadCredentials
from app.data.query_budget import QueryCapacityExceeded, QueryDeadlineExceeded, execute_bounded


class DataAccessError(RuntimeError):
    pass


class ExportBudgetError(DataAccessError):
    pass


def guard_select(query: str) -> None:
    try:
        statements = sqlglot.parse(query, read="databricks")
    except sqlglot.errors.ParseError:
        raise ValueError("Invalid read-only SQL") from None
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Only a single SELECT is allowed")
    tree = statements[0]
    for node in tree.walk():
        if isinstance(node, (exp.DDL, exp.DML, exp.Command, exp.Into)):
            raise ValueError("Non-read-only expression rejected")


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("Invalid SQL identifier")
    return f"`{value}`"


def table_name(settings: Settings, table: str) -> str:
    return ".".join(
        identifier(x) for x in (settings.databricks_catalog, settings.databricks_schema, table)
    )


class DatabricksClient:
    def __init__(self, settings: Settings, connect=None):
        self.settings = settings
        self._connect = connect

    def select(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
        *,
        max_rows: int,
        max_bytes: int = 64_000_000,
    ) -> pd.DataFrame:
        guard_select(query)
        if max_rows < 1 or max_bytes < 1:
            raise ValueError("Positive export budgets required")
        cfg = self.settings
        if not all(
            [
                cfg.databricks_server_hostname,
                cfg.databricks_http_path,
                cfg.databricks_client_id,
            ]
        ):
            raise DataAccessError("Databricks connection configuration is incomplete")
        try:
            credentials = WorkloadCredentials(cfg)
        except WorkloadAuthenticationError as error:
            raise DataAccessError(str(error)) from None
        connect = self._connect
        if connect is None:
            from databricks import sql

            connect = sql.connect
        if parameters and "__rmi_row_limit" in parameters:
            raise ValueError("Reserved query parameter")
        canonical = sqlglot.parse_one(query, read="databricks").sql(dialect="databricks")
        bounded_query = f"SELECT * FROM ({canonical}) AS __rmi_bounded LIMIT :__rmi_row_limit"
        bounded_parameters = {**(parameters or {}), "__rmi_row_limit": max_rows + 1}

        def operation(cancelled, attach):
            try:
                return self._select_connected(
                    connect,
                    credentials,
                    bounded_query,
                    bounded_parameters,
                    max_rows,
                    max_bytes,
                    cancelled,
                    attach,
                )
            except DataAccessError:
                raise
            except Exception:
                raise DataAccessError("Databricks SELECT failed; diagnostics suppressed") from None

        try:
            return execute_bounded(
                (cfg.databricks_server_hostname, cfg.databricks_http_path),
                cfg.databricks_max_concurrent_queries,
                cfg.databricks_queue_timeout_seconds,
                cfg.databricks_query_timeout_seconds,
                operation,
            )
        except (QueryCapacityExceeded, QueryDeadlineExceeded) as error:
            raise DataAccessError(str(error)) from None

    def _select_connected(
        self, connect, credentials, query, parameters, max_rows, max_bytes, cancelled, attach
    ):
        cfg = self.settings
        with (
            closing(
                connect(
                    server_hostname=cfg.databricks_server_hostname,
                    http_path=cfg.databricks_http_path,
                    credentials_provider=credentials,
                    use_inline_params=False,
                    session_configuration={
                        "STATEMENT_TIMEOUT": str(math.ceil(cfg.databricks_query_timeout_seconds))
                    },
                    _socket_timeout=min(cfg.databricks_query_timeout_seconds, 15),
                    _retry_stop_after_attempts_count=1,
                )
            ) as connection,
            closing(connection.cursor()) as cursor,
        ):
            attach(cursor)
            cursor.execute("SELECT current_user() AS workload_identity")
            identity = cursor.fetchone()
            if identity is None or identity[0] != cfg.databricks_client_id:
                raise DataAccessError("SQL session does not match the configured workload identity")
            if cancelled.is_set():
                raise QueryDeadlineExceeded("Query cancelled before execution")
            cursor.execute(query, parameters=parameters or {})
            columns = [x[0] for x in cursor.description]
            chunks = []
            rows = size = 0
            while True:
                if cancelled.is_set():
                    raise QueryDeadlineExceeded("Query cancelled during fetch")
                batch = cursor.fetchmany(min(1000, max_rows + 1 - rows))
                if not batch:
                    break
                frame = pd.DataFrame.from_records(batch, columns=columns)
                rows += len(frame)
                size += int(frame.memory_usage(deep=True).sum())
                if rows > max_rows or size > max_bytes:
                    try:
                        cursor.cancel()
                    except Exception:
                        pass
                    raise ExportBudgetError(
                        "Export exceeds row or memory budget; no partial result"
                    )
                chunks.append(frame)
            return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=columns)
