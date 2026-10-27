"""Pure ASGI controls applied before JSON parsing; fixed-size global rate buckets, no client map."""

import logging
import math
import threading
import time
from collections import deque
from urllib.parse import urlsplit
from uuid import uuid4

from starlette.responses import JSONResponse

from app.core.service_auth import (
    PROTECTED_PATHS,
    SERVICE_HEADER,
    ServiceAuthError,
    verify_service_key,
)

logger = logging.getLogger(__name__)


class RateBudgets:
    def __init__(self, cfg, clock=time.monotonic):
        self.window = cfg.rate_limit_window_seconds
        self.limits = {
            "inference": cfg.rate_limit_inference,
            "write": cfg.rate_limit_write,
            "read": cfg.rate_limit_read,
        }
        self.buckets = {name: deque() for name in self.limits}
        self.clock, self.lock = clock, threading.Lock()

    def admit(self, category):
        now = self.clock()
        with self.lock:
            bucket = self.buckets[category]
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limits[category]:
                return max(1, math.ceil(bucket[0] + self.window - now))
            bucket.append(now)
            return 0


class HttpSecurity:
    def __init__(self, app, cfg):
        self.app, self.cfg = app, cfg
        self.rates = RateBudgets(cfg)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = str(uuid4())
        path, method = scope["path"], scope["method"]
        status, response_started = 500, False
        category = "handled"

        async def secured_send(message):
            nonlocal status, response_started, category
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                if category == "handled" and status >= 400:
                    category = {
                        400: "request_rejected",
                        401: "auth_denied",
                        413: "body_limit",
                        422: "schema_rejected",
                        429: "rate_limit",
                        503: "service_unavailable",
                        504: "dependency_timeout",
                    }.get(status, "request_failed")
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"cache-control", b"x-request-id"}
                ]
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"cache-control", b"no-store"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-request-id", request_id.encode()),
                ]
                message = {**message, "headers": headers}
            await send(message)

        async def reject(code, detail, headers=None):
            await JSONResponse({"detail": detail}, status_code=code, headers=headers)(
                scope, receive, secured_send
            )

        try:
            headers = scope.get("headers", [])
            hosts = [v.decode("latin1") for k, v in headers if k.lower() == b"host"]
            try:
                host = urlsplit("//" + hosts[0]) if len(hosts) == 1 else None
                host_ok = (
                    host
                    and not host.username
                    and not host.password
                    and not host.path
                    and not host.query
                    and not host.fragment
                    and (host.port is None or 1 <= host.port <= 65535)
                    and host.hostname in self.cfg.allowed_hosts
                )
            except ValueError:
                host_ok = False
            if not host_ok:
                return await reject(400, "Invalid host")
            if path in PROTECTED_PATHS and method != "OPTIONS":
                keys = [
                    v.decode("latin1")
                    for k, v in headers
                    if k.lower() == SERVICE_HEADER.lower().encode()
                ]
                try:
                    verify_service_key(self.cfg, keys[0] if len(keys) == 1 else None)
                except ServiceAuthError as error:
                    return await reject(error.status, str(error))
                scope.setdefault("state", {})["service_authenticated"] = True
            if (path, method) != ("/health", "GET") and method != "OPTIONS":
                bucket = (
                    "inference"
                    if path in {"/predict", "/predict/batch", "/predictions/current"}
                    else ("write" if path == "/predictions/current/persist" else "read")
                )
                wait = self.rates.admit(bucket)
                if wait:
                    return await reject(429, "Request budget exhausted", {"Retry-After": str(wait)})
            if method in {"POST", "PUT", "PATCH"}:
                lengths = [v for k, v in headers if k.lower() == b"content-length"]
                try:
                    if lengths and any(k.lower() == b"transfer-encoding" for k, v in headers):
                        raise ValueError
                    if len(lengths) > 1 or (lengths and int(lengths[0]) < 0):
                        raise ValueError
                    if lengths and int(lengths[0]) > self.cfg.request_max_bytes:
                        return await reject(413, "Request body exceeds configured limit")
                except ValueError:
                    return await reject(400, "Invalid request framing")
                content = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    if message["type"] != "http.request":
                        return await reject(400, "Invalid request framing")
                    chunk = message.get("body", b"")
                    if len(content) + len(chunk) > self.cfg.request_max_bytes:
                        return await reject(413, "Request body exceeds configured limit")
                    content.extend(chunk)
                    if not message.get("more_body", False):
                        break
                delivered = False

                async def bounded_receive():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(content), "more_body": False}
                    return await receive()

                await self.app(scope, bounded_receive, secured_send)
            else:
                await self.app(scope, receive, secured_send)
        except Exception:
            category = "internal_error"
            if not response_started:
                await reject(500, "Request could not be completed")
        finally:
            endpoint = path if path in PROTECTED_PATHS | {"/health", "/ready"} else "unmatched"
            logger.info(
                "api_request request_id=%s method=%s endpoint=%s "
                "status=%d latency_ms=%.1f category=%s",
                request_id,
                method if method in {"GET", "POST", "OPTIONS"} else "OTHER",
                endpoint,
                status,
                (time.monotonic() - started) * 1000,
                category,
            )
