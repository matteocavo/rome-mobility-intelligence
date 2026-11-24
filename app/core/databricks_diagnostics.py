"""Bounded diagnostics: fixed categories and conservative redacted HTTP 400 details."""

import json
import re
import socket
import urllib.error
from uuid import uuid4

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



# Unknown words are withheld: raw upstream text can contain unlabelled names/secrets.
_MESSAGE_WORDS = frozenset("""
a an the this that these those is are was were be been being has have had do does did
not no cannot can could must should may will would only and or but if then when while
for from to with without in on at of by as because due before after please try again
request invalid bad malformed missing required parameter parameters value values
unsupported operation method endpoint api sql warehouse warehouses serverless compute
cluster clusters session sessions open start starting stopped stop running available
unavailable temporarily resource resources limit limits quota daily monthly free edition
exceeded exhausted capacity insufficient maximum minimum concurrent concurrency active
workspace workspaces account user users principal service access permission permissions
permitted denied allowed authorized unauthorized authentication authorization token scope
scopes expired disabled enabled configured configuration error failure failed internal
state status does exist found unknown use manage owner admin admins administrator
administrators feature features supported support upgrade plan billing suspended reached
provision provisioning unable failed unable successfully current multiple single all
entitlement entitlements must contains contain valid expected provided specified payload
body empty json forbidden permission_denied resource_exhausted bad_request
""".split())


def sanitized_message(value):
    """Lossy diagnostic projection, never raw body, arbitrary identifiers or numbers."""
    if type(value) is not str or not value:
        return "unavailable"
    text = value[:4096]
    # Remove whole credential/URL/quoted spans before retaining diagnostic vocabulary.
    text = re.sub(r"(?i)\b(?:https?://|jdbc:|postgres(?:ql)?://)\S+", " [redacted] ", text)
    text = re.sub(r"(?i)\b(?:authorization|proxy-authorization)\s*[:=][^\r\n]*",
                  " [redacted] ", text)
    text = re.sub(r"(?i)\b(?:bearer|basic)\s+\S+", " [redacted] ", text)
    text = re.sub(r"(?i)\b(?:password|passwd|pwd|secret|token|client_secret|api_key|"
                  r"access_token|connection_string)\s*[:=]\s*[^\s,;]+", " [redacted] ", text)
    text = re.sub(r"[\"'][^\"']*[\"']", " [redacted] ", text)
    text = re.sub(r"\S*@\S*", " [redacted] ", text)
    words = []
    for word in re.findall(r"[A-Za-z_]+|[^\sA-Za-z_]+", text):
        safe = word if word.lower() in _MESSAGE_WORDS else "[redacted]"
        if safe != "[redacted]" or not words or words[-1] != safe:
            words.append(safe)
    return " ".join(words)[:512] or "unavailable"


def sanitized_request_id(value):
    # UUIDs and hex trace IDs only, never arbitrary header values.
    if type(value) is str and re.fullmatch(
        r"(?:[a-fA-F0-9]{16}|[a-fA-F0-9]{32}|"
        r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})", value
    ):
        return value
    return "unavailable"


def _safe_details(error, payload=None):
    context = getattr(error, "context", {})
    context = context if isinstance(context, dict) else {}
    value = payload if isinstance(payload, dict) else context
    message = value.get("message", value.get("error-message"))
    request_id = value.get("request_id", value.get("request-id"))
    if isinstance(error, urllib.error.HTTPError):
        headers = error.headers
        if headers is not None:
            request_id = (
                headers.get("X-Databricks-Request-Id")
                or headers.get("X-Request-Id")
                or request_id
            )
    return {"message": sanitized_message(message),
            "databricks_request_id": sanitized_request_id(request_id)}


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
    value = None
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
    if failure_metadata(error)[0] == 400:
        try:
            error._rmi_safe_details = _safe_details(error, value)
        except Exception:
            error._rmi_safe_details = {
                "message": "unavailable", "databricks_request_id": "unavailable",
            }
    return code


# Free daily limit rejection: HTTP 400 plus all three vocabulary signals, in order.
_DAILY_QUOTA_MESSAGE = re.compile(r"\bfree\b.{0,60}\bdaily\b.{0,60}\blimit\b", re.IGNORECASE)


def is_daily_quota_exhausted(error):
    """True only for the Free Edition daily-limit rejection (never for other HTTP 400s).

    Requires, on one and the same exception: HTTP status 400, an allowlisted
    BAD_REQUEST code (or no code on an OpenSession rejection, where the connector
    does not expose one) and the sanitized message containing "free ... daily ... limit".
    Only the lossy sanitized projection is inspected; nothing raw is returned.
    """
    pending, seen = [error], set()
    while pending and len(seen) < 8:
        item = pending.pop(0)
        if id(item) in seen or not isinstance(item, BaseException):
            continue
        seen.add(id(item))
        try:
            status, rpc = failure_metadata(item)
            if status == 400:
                code = failure_error_code(item)
                if code == "BAD_REQUEST" or (code == "unknown" and rpc == "open_session"):
                    details = getattr(item, "_rmi_safe_details", None) or {}
                    message = details.get("message")
                    if type(message) is str and _DAILY_QUOTA_MESSAGE.search(message):
                        return True
        except Exception:
            # Classification must never replace the original failure.
            pass
        context = getattr(item, "context", {})
        context = context if isinstance(context, dict) else {}
        for nested in (context.get("original-exception"), item.__cause__):
            if isinstance(nested, BaseException):
                pending.append(nested)
    return False


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
    if status == 400 and operation in {"session_open", "warehouse_start"}:
        try:
            detail = getattr(error, "_rmi_safe_details", None) or _safe_details(error)
            logger.warning("databricks_http400_detail %s", json.dumps({
                "operation": operation, "http_status": status,
                "error_code": failure_error_code(error), **detail,
                "local_correlation_id": str(uuid4()),
            }, sort_keys=True))
        except Exception:
            # Diagnostics must never replace the original connection failure.
            logger.warning("databricks_http400_detail unavailable")
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
