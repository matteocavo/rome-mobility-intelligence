"""Actions HTTPS client: fixed routes, bounded retries, no DB/warehouse credentials."""

import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

MAX_RESPONSE = 65536
WARM_BUDGET = 240
WARM_DELAYS = (30, 45, 45, 45, 0)
SAFE_STAGES = frozenset(
    {
        "configuration",
        "health",
        "ready",
        "persistence",
        "persistence_response",
        "transport",
        "response",
        "internal",
    }
)
READY_FLAGS = (
    "model_ready",
    "workload_identity_configured",
    "database_configured",
    "prediction_persistence_enabled",
)
SAFE_CATEGORIES = frozenset(
    {
        "authentication_or_authorization",
        "client_error",
        "configuration",
        "connectivity_or_timeout",
        "invalid_json_shape",
        "invalid_persistence_response",
        "not_found",
        "rate_limited",
        "response_parse_error",
        "response_too_large",
        "server_error",
        "server_unavailable_or_timeout",
        "transport_error",
        "truncated_response",
        "unknown",
    }
)
SAFE_PATHS = frozenset(
    {"/health", "/ready", "/predictions/current/persist?limit=100", "/predictions/history?limit=10"}
)


def classify_status(status):
    if status == 0:
        return "connectivity_or_timeout"
    if status in (401, 403):
        return "authentication_or_authorization"
    if status == 404:
        return "not_found"
    if status == 429:
        return "rate_limited"
    if status in (502, 503, 504):
        return "server_unavailable_or_timeout"
    if 500 <= status < 600:
        return "server_error"
    if 400 <= status < 500:
        return "client_error"
    return "unknown"


def safe_stage(stage):
    return stage if type(stage) is str and stage in SAFE_STAGES else "internal"


def safe_category(category, status=None):
    if type(category) is str and category in SAFE_CATEGORIES:
        return category
    return classify_status(safe_status(status))


def safe_status(status):
    return status if type(status) is int and (status == 0 or 100 <= status <= 599) else 0


def safe_path(path):
    return path if type(path) is str and path in SAFE_PATHS else None


class OrchestrationError(RuntimeError):
    def __init__(self, stage, *, path=None, status=None, category=None):
        self.stage = safe_stage(stage)
        self.path = safe_path(path)
        self.status = safe_status(status)
        self.category = safe_category(category, self.status)
        super().__init__(f"Prediction orchestration failed: {self.stage}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base_url, key, *, opener=None, clock=time.monotonic, sleep=time.sleep):
        try:
            url = urlsplit(base_url)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.port not in {None, 443}
                or url.username
                or url.password
                or url.path not in {"", "/"}
                or url.query
                or url.fragment
                or not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,}", url.hostname)
                or url.hostname.endswith((".invalid", ".local", ".internal", ".localhost"))
                or any(c.isspace() for c in base_url)
                or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", key)
            ):
                raise ValueError
        except Exception:
            raise OrchestrationError("configuration") from None
        self.base, self.key = base_url.rstrip("/"), key
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        self.clock, self.sleep = clock, sleep
        self.last_failure = None

    def _record_failure(self, stage, path, status, category=None):
        self.last_failure = {
            "stage": safe_stage(stage),
            "path": safe_path(path),
            "status": safe_status(status),
            "category": safe_category(category, safe_status(status)),
        }

    def request(self, path, *, method="GET", timeout=15):
        request = urllib.request.Request(
            self.base + path,
            method=method,
            headers={"X-RMI-Service-Key": self.key, "Accept": "application/json"},
        )
        status = 0
        try:
            deadline = self.clock() + timeout
            with self.opener.open(request, timeout=timeout) as response:
                status = safe_status(response.status)
                if response.status != 200:
                    return response.status, None
                data = bytearray()
                length = response.headers.get("Content-Length")
                if length and (not length.isdigit() or int(length) > MAX_RESPONSE):
                    raise OrchestrationError(
                        "response", path=path, status=response.status, category="response_too_large"
                    )
                while True:
                    remaining = deadline - self.clock()
                    if remaining <= 0:
                        raise TimeoutError
                    response.fp.raw._sock.settimeout(remaining)
                    block = response.read1(min(65536, MAX_RESPONSE - len(data) + 1))
                    if not block:
                        break
                    data.extend(block)
                    if len(data) > MAX_RESPONSE:
                        raise OrchestrationError(
                            "response",
                            path=path,
                            status=response.status,
                            category="response_too_large",
                        )
                    if length and len(data) == int(length):
                        break
                if length and len(data) != int(length):
                    raise OrchestrationError(
                        "response", path=path, status=response.status, category="truncated_response"
                    )
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise OrchestrationError(
                        "response", path=path, status=response.status, category="invalid_json_shape"
                    )
                return response.status, value
        except urllib.error.HTTPError as error:
            error.close()
            return error.code, None
        except (TimeoutError, socket.timeout):
            return 0, None
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                return 0, None
            raise OrchestrationError(
                "transport", path=path, status=0, category="transport_error"
            ) from None
        except OrchestrationError:
            raise
        except Exception:
            raise OrchestrationError(
                "response", path=path, status=status, category="response_parse_error"
            ) from None

    def warm(self, path, predicate, stage, *, deadline=None):
        deadline = self.clock() + WARM_BUDGET if deadline is None else deadline
        status = 0
        for attempt, delay in enumerate(WARM_DELAYS):
            remaining = deadline - self.clock()
            if remaining <= 0:
                break
            status, data = self.request(path, timeout=min(15, remaining))
            if status == 200 and predicate(data):
                return
            if status not in {0, 502, 503, 504} and not (path == "/ready" and status == 200):
                self._record_failure(stage, path, status)
                raise OrchestrationError(stage, path=path, status=status)
            if attempt < len(WARM_DELAYS) - 1 and deadline - self.clock() > delay:
                self.sleep(delay)
            else:
                break
        self._record_failure(stage, path, status)
        raise OrchestrationError(stage, path=path, status=status)

    def run(self, *, history=False):
        deadline = self.clock() + WARM_BUDGET
        self.warm("/health", lambda d: d.get("status") == "ok", "health", deadline=deadline)
        self.warm(
            "/ready",
            lambda d: (
                d.get("status") == "ready"
                and all(d.get(k) is True for k in READY_FLAGS)
                and d.get("artifact_integrity") == "verified"
            ),
            "ready",
            deadline=deadline,
        )
        for attempt, delay in enumerate((30, 60, 0)):
            status, data = self.request(
                "/predictions/current/persist?limit=100", method="POST", timeout=140
            )
            if status == 200:
                values = [data.get(k) for k in ("rows_evaluated", "rows_inserted", "rows_existing")]
                if (
                    any(type(v) is not int or v < 0 or v > 100 for v in values)
                    or values[1] + values[2] != values[0]
                ):
                    raise OrchestrationError(
                        "persistence_response",
                        path="/predictions/current/persist?limit=100",
                        status=status,
                        category="invalid_persistence_response",
                    )
                summary = dict(
                    zip(("rows_evaluated", "rows_inserted", "rows_existing"), values, strict=True)
                )
                summary["status"] = "success_idempotent" if values[1] == 0 else "success"
                summary["retry_count"] = attempt
                if history:
                    try:
                        code, _ = self.request("/predictions/history?limit=10", timeout=10)
                        summary["history_followup_ok"] = code == 200
                    except OrchestrationError:
                        summary["history_followup_ok"] = False
                return summary
            self._record_failure("persistence", "/predictions/current/persist?limit=100", status)
            if status not in {0, 503, 504} or attempt == 2:
                category = classify_status(status)
                if status in (401, 403):
                    category = "authentication_or_authorization"
                raise OrchestrationError(
                    "persistence",
                    path="/predictions/current/persist?limit=100",
                    status=status,
                    category=category,
                )
            self.sleep(delay)
        self._record_failure("persistence", "/predictions/current/persist?limit=100", 0)
        raise OrchestrationError(
            "persistence", path="/predictions/current/persist?limit=100", status=0
        )


def main():
    client = None
    try:
        client = Client(
            os.environ.get("RMI_API_BASE_URL", ""), os.environ.get("RMI_SERVICE_API_KEY", "")
        )
        print(json.dumps(client.run(history=os.environ.get("RMI_FETCH_HISTORY") == "true")))
    except OrchestrationError as error:
        detail = {
            "stage": safe_stage(error.stage),
            "path": safe_path(error.path),
            "status": safe_status(error.status),
            "category": safe_category(error.category, safe_status(error.status)),
        }
        detail = {k: v for k, v in detail.items() if v is not None}
        print(json.dumps(detail), file=sys.stderr)
        raise SystemExit(f"Prediction orchestration failed: {safe_stage(error.stage)}") from None
    except Exception:
        raise SystemExit("Prediction orchestration failed: internal") from None


if __name__ == "__main__":
    main()
