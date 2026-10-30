"""Fixed diagnostic categories only; never emit upstream messages or context."""

import re
import socket
import urllib.error

CATEGORIES = frozenset({
    "databricks_authentication", "databricks_authorization",
    "databricks_compute_unavailable", "databricks_timeout",
    "databricks_query_error", "databricks_connectivity",
    "databricks_configuration", "databricks_unknown",
})


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
        if isinstance(item, (ConnectionError, urllib.error.URLError, OSError)):
            nested = getattr(item, "reason", None)
            if isinstance(nested, (TimeoutError, socket.timeout)):
                return "databricks_timeout"
            return "databricks_connectivity"
        for nested in (context.get("original-exception"), item.__cause__, item.__context__):
            if isinstance(nested, BaseException):
                pending.append(nested)
        if isinstance(state, str) and state.startswith(("42", "22")):
            return "databricks_query_error"
        if type(item).__name__ in {"ServerOperationError", "ProgrammingError", "DataError"}:
            return "databricks_query_error"
    return "databricks_unknown"
