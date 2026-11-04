"""Fixed diagnostic categories only; never emit upstream messages or context."""

import json
import re
import socket
import urllib.error

CATEGORIES = frozenset({
    "databricks_authentication", "databricks_authorization",
    "databricks_compute_unavailable", "databricks_timeout",
    "databricks_query_error", "databricks_connectivity",
    "databricks_configuration", "databricks_unknown", "databricks_http_error",
})

ERROR_CODES = frozenset({
    "BAD_REQUEST", "INVALID_PARAMETER_VALUE", "INVALID_STATE", "RESOURCE_DOES_NOT_EXIST",
    "PERMISSION_DENIED", "UNAUTHENTICATED", "TEMPORARILY_UNAVAILABLE",
    "RESOURCE_EXHAUSTED", "QUOTA_EXCEEDED", "REQUEST_LIMIT_EXCEEDED", "INTERNAL_ERROR",
})
OPERATIONS = frozenset({
    "session_open", "warehouse_get", "warehouse_start", "warehouse_poll", "select",
})
WAREHOUSE_STATES = frozenset({"STOPPED", "STARTING", "RUNNING", "STOPPING", "DELETED"})


def failure_error_code(error):
    """Read at most 4 KiB of an HTTP rejection, retaining only an allowlisted code.

    Never inspect implicit exception context: it can belong to an earlier request.
    Cache only the sanitized code so classification/logging cannot drain the body twice.
    """
    cached = getattr(error, "_rmi_error_code", None)
    if type(cached) is str:
        return cached if cached in ERROR_CODES else "unknown"
    context = getattr(error, "context", {})
    context = context if isinstance(context, dict) else {}
    code = context.get("error_code", context.get("error-code"))
    if isinstance(error, urllib.error.HTTPError):
        try:
            payload = error.read(4097)
            value = json.loads(payload) if len(payload) <= 4096 else None
            code = value.get("error_code") if isinstance(value, dict) else None
        except Exception:
            # Diagnostics must not replace a rejection if its body is unreadable.
            code = None
    code = code if type(code) is str and code in ERROR_CODES else "unknown"
    error._rmi_error_code = code
    return code


def log_failure(logger, error, operation, elapsed_ms, *, warehouse_state="unknown", attempt=1):
    """One sanitized event per failed operation; the outer SELECT handler skips repeats."""
    status, rpc = failure_metadata(error)
    logger.warning(
        "databricks_failure stage=select operation=%s category=%s "
        "http_status=%d rpc=%s error_code=%s warehouse_state=%s elapsed_ms=%d attempt=%d",
        operation if type(operation) is str and operation in OPERATIONS else "unknown",
        failure_category(error), status, rpc, failure_error_code(error),
        warehouse_state if type(warehouse_state) is str and warehouse_state in WAREHOUSE_STATES
        else "unknown",
        elapsed_ms, attempt,
    )
    error._rmi_failure_logged = True


def failure_metadata(error):
    """Fixed RPC name and numeric HTTP status; never export connector context."""
    pending, seen = [error], set()
    methods = {"OpenSession": "open_session", "ExecuteStatement": "execute_statement",
               "FetchResults": "fetch_results", "CloseSession": "close_session"}
    while pending and len(seen) < 8:
        item = pending.pop(0)
        if id(item) in seen:
            continue
        seen.add(id(item))
        context = getattr(item, "context", {})
        context = context if isinstance(context, dict) else {}
        code = item.code if isinstance(item, urllib.error.HTTPError) else context.get("http-code")
        status = code if type(code) is int and 100 <= code <= 599 else 0
        if isinstance(item, urllib.error.HTTPError):
            return status, "unknown"
        method = context.get("method")
        rpc = methods.get(method, "unknown") if type(method) is str else "unknown"
        if status or rpc != "unknown":
            # Status and RPC must come from this request, never separate exceptions.
            return status, rpc
        for nested in (context.get("original-exception"), item.__cause__):
            if isinstance(nested, BaseException):
                pending.append(nested)
    return 0, "unknown"


def failure_category(error):
    """Inspect known connector metadata/chains but return only an allowlisted constant."""
    pending, seen = [error], set()
    while pending and len(seen) < 8:
        item = pending.pop(0)
        if id(item) in seen:
            continue
        seen.add(id(item))
        category = getattr(item, "category", None)
        if isinstance(category, str) and category in CATEGORIES:
            return category
        context = getattr(item, "context", {})
        context = context if isinstance(context, dict) else {}
        status = item.code if isinstance(item, urllib.error.HTTPError) else context.get("http-code")
        if status == 401:
            return "databricks_authentication"
        if status == 403:
            return "databricks_authorization"
        if status in (408, 504) or isinstance(item, (TimeoutError, socket.timeout)):
            return "databricks_timeout"
        if status in (429, 502, 503):
            return "databricks_compute_unavailable"
        code = failure_error_code(item)
        if code == "UNAUTHENTICATED":
            return "databricks_authentication"
        if code == "PERMISSION_DENIED":
            return "databricks_authorization"
        if code in {"RESOURCE_EXHAUSTED", "QUOTA_EXCEEDED", "TEMPORARILY_UNAVAILABLE"}:
            return "databricks_compute_unavailable"
        state = getattr(item, "sqlstate", None) or context.get("sql-state")
        if isinstance(state, str) and state.startswith("28"):
            return "databricks_authentication"
        if state == "42501":
            return "databricks_authorization"
        # Messages are examined only for fixed service signals, never returned/logged.
        private = str(item) + " " + str(context.get("error-message", ""))
        if re.search(
            r"(?:DAILY[_ ]LIMIT|QUOTA_EXCEEDED|RESOURCE_EXHAUSTED|"
            r"(?:free|daily|monthly).{0,80}\blimit\b)", private, re.IGNORECASE,
        ):
            return "databricks_compute_unavailable"
        if isinstance(state, str) and state.startswith(("42", "22")):
            return "databricks_query_error"
        if type(item).__name__ in {"ServerOperationError", "ProgrammingError", "DataError"}:
            return "databricks_query_error"
        if isinstance(item, urllib.error.HTTPError) or (
            type(status) is int and 400 <= status <= 599
        ):
            return "databricks_http_error"
        if isinstance(item, (ConnectionError, urllib.error.URLError, OSError)):
            nested = getattr(item, "reason", None)
            if isinstance(nested, (TimeoutError, socket.timeout)):
                return "databricks_timeout"
            return "databricks_connectivity"
        for nested in (context.get("original-exception"), item.__cause__):
            if isinstance(nested, BaseException):
                pending.append(nested)
    return "databricks_unknown"
