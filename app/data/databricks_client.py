"""Bounded SELECT transport. Workspace least-privilege grants remain required."""

import logging
import math
import re
import time
from contextlib import closing
from typing import Any

import pandas as pd
import sqlglot
from sqlglot import exp

from app.core.config import Settings
from app.core.databricks_diagnostics import failure_category
from app.core.workload_auth import WorkloadAuthenticationError, WorkloadCredentials
from app.data.query_budget import QueryCapacityExceeded, QueryDeadlineExceeded, execute_bounded

logger = logging.getLogger(__name__)


class DataAccessError(RuntimeError):
    pass


class ExportBudgetError(DataAccessError):
    pass


class QueryTimeoutError(DataAccessError):
    """Application deadline expired and cancellation was requested."""


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
        compact_strings: bool = False,
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
            started = time.perf_counter()
            try:
                frame, timings = self._select_connected(
                    connect,
                    credentials,
                    bounded_query,
                    bounded_parameters,
                    max_rows,
                    max_bytes,
                    cancelled,
                    attach,
                    compact_strings,
                )
                logger.info(
                    "databricks_select_timing rows=%d dataframe_bytes=%d connection_auth_ms=%d "
                    "identity_check_ms=%d sql_execute_ms=%d first_batch_ms=%d "
                    "fetch_transfer_ms=%d fetch_complete_ms=%d dataframe_conversion_ms=%d "
                    "total_ms=%d",
                    len(frame),
                    int(frame.memory_usage(deep=True).sum()),
                    *timings,
                    round((time.perf_counter() - started) * 1000),
                )
                return frame
            except DataAccessError:
                raise
            except Exception as error:
                category = failure_category(error)
                logger.warning(
                    "databricks_failure stage=select category=%s elapsed_ms=%d",
                    category,
                    round((time.perf_counter() - started) * 1000),
                )
                raise DataAccessError("Databricks SELECT failed; diagnostics suppressed") from None

        try:
            return execute_bounded(
                (cfg.databricks_server_hostname, cfg.databricks_http_path),
                cfg.databricks_max_concurrent_queries,
                cfg.databricks_queue_timeout_seconds,
                cfg.databricks_query_timeout_seconds,
                operation,
            )
        except QueryDeadlineExceeded as error:
            raise QueryTimeoutError(str(error)) from None
        except QueryCapacityExceeded as error:
            raise DataAccessError(str(error)) from None

    def _select_connected(
        self,
        connect,
        credentials,
        query,
        parameters,
        max_rows,
        max_bytes,
        cancelled,
        attach,
        compact_strings=False,
    ):
        cfg = self.settings
        connection_started = time.perf_counter()
        identity_ms = execute_ms = first_batch_ms = fetch_transfer_ms = 0
        fetch_complete_ms = conversion_ms = 0
        first_batch_recorded = False
        fetch_started = None
        with (
            closing(
                connect(
                    server_hostname=cfg.databricks_server_hostname,
                    http_path=cfg.databricks_http_path,
                    credentials_provider=credentials,
                    use_cloud_fetch=True,
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
            connection_ms = round((time.perf_counter() - connection_started) * 1000)
            attach(cursor)
            if compact_strings:
                # fetchmany(1000) alone does not bound the connector's internal
                # direct-result buffer (default arraysize is 10,000).
                cursor.arraysize = 1000
            stage_started = time.perf_counter()
            cursor.execute("SELECT current_user() AS workload_identity")
            identity = cursor.fetchone()
            identity_ms = round((time.perf_counter() - stage_started) * 1000)
            if identity is None or identity[0] != cfg.databricks_client_id:
                raise DataAccessError("SQL session does not match the configured workload identity")
            if cancelled.is_set():
                raise QueryDeadlineExceeded("Query cancelled before execution")
            stage_started = time.perf_counter()
            cursor.execute(query, parameters=parameters or {})
            execute_ms = round((time.perf_counter() - stage_started) * 1000)
            fetch_started = time.perf_counter()
            columns = [x[0] for x in cursor.description]
            chunks = []
            rows = size = 0
            while True:
                if cancelled.is_set():
                    raise QueryDeadlineExceeded("Query cancelled during fetch")
                batch_started = time.perf_counter()
                batch = cursor.fetchmany(min(1000, max_rows + 1 - rows))
                batch_ms = round((time.perf_counter() - batch_started) * 1000)
                if not first_batch_recorded:
                    first_batch_ms = batch_ms
                    first_batch_recorded = True
                fetch_transfer_ms += batch_ms
                if not batch:
                    break
                conversion_started = time.perf_counter()
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
                if compact_strings:
                    # Budget uses the ORIGINAL deep size above. Dictionary encoding
                    # changes storage only, never values, nulls or security checks.
                    for name in frame.select_dtypes(include="object").columns:
                        if frame[name].nunique(dropna=False) <= 64:
                            frame[name] = frame[name].astype("category")
                chunks.append(frame)
                conversion_ms += round((time.perf_counter() - conversion_started) * 1000)
                del batch
            result = (
                pd.concat(chunks, ignore_index=True)
                if chunks
                else pd.DataFrame(columns=columns)
            )
            fetch_complete_ms = round((time.perf_counter() - fetch_started) * 1000)
            return result, (
                connection_ms,
                identity_ms,
                execute_ms,
                first_batch_ms,
                fetch_transfer_ms,
                fetch_complete_ms,
                conversion_ms,
            )
