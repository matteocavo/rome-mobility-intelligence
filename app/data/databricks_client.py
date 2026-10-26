"""Bounded SELECT transport. Workspace least-privilege grants remain required."""

import re
from contextlib import closing
from typing import Any

import pandas as pd
import sqlglot
from sqlglot import exp

from app.core.config import Settings
from app.core.workload_auth import WorkloadAuthenticationError, WorkloadCredentials


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
        try:
            with (
                closing(
                    connect(
                        server_hostname=cfg.databricks_server_hostname,
                        http_path=cfg.databricks_http_path,
                        credentials_provider=credentials,
                        use_inline_params=False,
                    )
                ) as connection,
                closing(connection.cursor()) as cursor,
            ):
                cursor.execute("SELECT current_user() AS workload_identity")
                identity = cursor.fetchone()
                if identity is None or identity[0] != cfg.databricks_client_id:
                    raise DataAccessError(
                        "SQL session does not match the configured workload identity"
                    )
                cursor.execute(query, parameters=parameters or {})
                columns = [x[0] for x in cursor.description]
                chunks = []
                rows = size = 0
                while True:
                    batch = cursor.fetchmany(min(1000, max_rows + 1 - rows))
                    if not batch:
                        break
                    frame = pd.DataFrame.from_records(batch, columns=columns)
                    rows += len(frame)
                    size += int(frame.memory_usage(deep=True).sum())
                    if rows > max_rows or size > max_bytes:
                        raise ExportBudgetError(
                            "Export exceeds row or memory budget; no partial result"
                        )
                    chunks.append(frame)
                return (
                    pd.concat(chunks, ignore_index=True)
                    if chunks
                    else pd.DataFrame(columns=columns)
                )
        except DataAccessError:
            raise
        except Exception:
            # Connector exceptions can contain SQL, hostnames and credentials.
            raise DataAccessError(
                "Databricks SELECT failed; inspect private connector diagnostics"
            ) from None
