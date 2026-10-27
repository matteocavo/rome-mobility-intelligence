"""Actions HTTPS client: fixed routes, bounded retries, no DB/warehouse credentials."""

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

MAX_RESPONSE = 65536
READY_FLAGS = (
    "model_ready",
    "workload_identity_configured",
    "database_configured",
    "prediction_persistence_enabled",
)


class OrchestrationError(RuntimeError):
    def __init__(self, stage):
        # Only fixed internal stage names; never interpolate network diagnostics.
        super().__init__(f"Prediction orchestration failed: {stage}")


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

    def request(self, path, *, method="GET", timeout=15):
        request = urllib.request.Request(
            self.base + path,
            method=method,
            headers={"X-RMI-Service-Key": self.key, "Accept": "application/json"},
        )
        try:
            deadline = self.clock() + timeout
            with self.opener.open(request, timeout=timeout) as response:
                if response.status != 200:
                    return response.status, None
                data = bytearray()
                length = response.headers.get("Content-Length")
                if length and (not length.isdigit() or int(length) > MAX_RESPONSE):
                    raise OrchestrationError("response")
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
                        raise OrchestrationError("response")
                    if length and len(data) == int(length):
                        break
                if length and len(data) != int(length):
                    raise OrchestrationError("response")
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise OrchestrationError("response")
                return 200, value
        except urllib.error.HTTPError as error:
            error.close()
            return error.code, None
        except (TimeoutError, socket.timeout):
            return 0, None
        except urllib.error.URLError as error:
            # Only actual transport timeouts can retry a write, not arbitrary TLS,
            # DNS, certificate or connection errors.
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                return 0, None
            raise OrchestrationError("transport") from None
        except Exception:
            raise OrchestrationError("response") from None

    def warm(self, path, predicate, stage):
        deadline = self.clock() + 120
        for attempt, delay in enumerate((30, 45, 0)):
            remaining = deadline - self.clock()
            if remaining <= 0:
                break
            status, data = self.request(path, timeout=min(15, remaining))
            if status == 200 and predicate(data):
                return
            if status not in {0, 502, 503, 504} and not (path == "/ready" and status == 200):
                raise OrchestrationError(stage)
            if attempt < 2 and deadline - self.clock() > delay:
                self.sleep(delay)
            else:
                break
        raise OrchestrationError(stage)

    def run(self, *, history=False):
        self.warm("/health", lambda d: d.get("status") == "ok", "health")
        self.warm(
            "/ready",
            lambda d: (
                d.get("status") == "ready"
                and all(d.get(k) is True for k in READY_FLAGS)
                and d.get("artifact_integrity") == "verified"
            ),
            "ready",
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
                    raise OrchestrationError("persistence_response")
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
            if status not in {0, 503, 504} or attempt == 2:
                raise OrchestrationError("persistence")
            self.sleep(delay)
        raise OrchestrationError("persistence")


def main():
    try:
        client = Client(
            os.environ.get("RMI_API_BASE_URL", ""), os.environ.get("RMI_SERVICE_API_KEY", "")
        )
        print(json.dumps(client.run(history=os.environ.get("RMI_FETCH_HISTORY") == "true")))
    except Exception:
        raise SystemExit("Prediction orchestration failed; diagnostics suppressed") from None


if __name__ == "__main__":
    main()
