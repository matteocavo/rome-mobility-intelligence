"""ASGI controls: bounded public client quotas; separate strict operational budgets."""

import hashlib
import logging
import math
import secrets
import threading
import time
from collections import OrderedDict, deque
from ipaddress import ip_address, ip_network
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
            "public": cfg.rate_limit_public_global,
        }
        self.buckets = {name: deque() for name in self.limits}
        self.clock, self.lock = clock, threading.Lock()
        self.public_limit = cfg.rate_limit_public
        self.client_cap = cfg.public_max_client_buckets
        self.clients = OrderedDict()
        self._hash_key = secrets.token_bytes(16)
        self.proxy_header = cfg.public_client_ip_header
        self.trusted_proxies = tuple(ip_network(value) for value in cfg.public_trusted_proxy_cidrs)

    def client_identity(self, scope):
        # Uvicorn proxy_headers stays disabled: scope.client is the actual socket peer.
        # Never consume X-Forwarded-For/Forwarded or arbitrary browser client IDs.
        peer = scope.get("client")
        try:
            address = ip_address(peer[0]) if peer else None
        except ValueError:
            address = None
        if (
            address is not None
            and self.proxy_header == "cf-connecting-ip"
            and any(address in network for network in self.trusted_proxies)
        ):
            supplied = [
                value
                for key, value in scope.get("headers", [])
                if key.lower() == b"cf-connecting-ip"
            ]
            # Fail closed on missing, repeated, chained, or invalid edge headers.
            try:
                if len(supplied) != 1 or len(supplied[0]) > 45:
                    raise ValueError
                forwarded = ip_address(supplied[0].decode("ascii"))
                if not forwarded.is_global:
                    raise ValueError
                address = forwarded
            except (ValueError, UnicodeError):
                return None
        if address is None:
            identity = "unknown-peer"
        elif address.version == 6:
            identity = str(ip_network((address, 64), strict=False))
        else:
            identity = str(address)
        # No plaintext visitor IPs or headers are kept/logged in the bucket table.
        return hashlib.blake2b(identity.encode(), key=self._hash_key, digest_size=16).digest()

    def admit(self, category, client=b"unknown-peer"):
        now = self.clock()
        with self.lock:
            if category == "public":
                if client is None:
                    return self.window
                entry = self.clients.get(client)
                if entry and now < entry[0] + self.window and entry[1] >= self.public_limit:
                    return max(1, math.ceil(entry[0] + self.window - now))
                if entry is None and len(self.clients) >= self.client_cap:
                    # Never evict an active quota: identity churn cannot reset limits.
                    expired = [
                        key for key, value in self.clients.items() if now >= value[0] + self.window
                    ]
                    for key in expired:
                        del self.clients[key]
                    if len(self.clients) >= self.client_cap:
                        return self.window
            bucket = self.buckets[category]
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limits[category]:
                return max(1, math.ceil(bucket[0] + self.window - now))
            bucket.append(now)
            if category == "public":
                start, count = self.clients.get(client, (now, 0))
                if now >= start + self.window:
                    start, count = now, 0
                self.clients[client] = (start, count + 1)
                self.clients.move_to_end(client)
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
                    "public"
                    if path.startswith("/public/")
                    else "inference"
                    if path in {"/predict", "/predict/batch", "/predictions/current"}
                    else ("write" if path == "/predictions/current/persist" else "read")
                )
                wait = (
                    self.rates.admit(bucket, self.rates.client_identity(scope))
                    if bucket == "public"
                    else self.rates.admit(bucket)
                )
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
