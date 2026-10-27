"""Authenticated, bounded Cloud webhook acknowledgement boundary, disabled without config."""

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from app.core.config import Settings


class N8nUnavailable(RuntimeError):
    pass


class N8nTimeout(N8nUnavailable):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WebhookAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: bool
    request_id: UUID


def trusted_webhook_url(settings: Settings) -> str:
    raw = settings.n8n_webhook_url.get_secret_value()
    try:
        if not raw or any(c.isspace() or ord(c) < 32 for c in raw) or "\\" in raw:
            raise ValueError
        url = urllib.parse.urlsplit(raw)
        host = settings.n8n_webhook_allowed_host
        if url.username or url.password or url.query or url.fragment:
            raise ValueError
        test = settings.environment == "test" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        if test:
            if url.scheme not in {"http", "https"}:
                raise ValueError
        elif (
            url.scheme != "https"
            or url.port not in {None, 443}
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.app\.n8n\.cloud", host)
            or url.hostname != host
        ):
            raise ValueError
        if not re.fullmatch(r"/webhook(?:-test)?/[a-zA-Z0-9_-]+", url.path):
            raise ValueError
        return raw
    except (ValueError, TypeError):
        raise N8nUnavailable("n8n webhook configuration is invalid") from None


class N8nClient:
    def __init__(self, settings: Settings, *, opener=None):
        self._settings = settings
        self._opener = opener

    def notify_prediction_orchestration(self) -> WebhookAcknowledgement:
        # No URL, payload or header is accepted from an HTTP request/caller.
        url = trusted_webhook_url(self._settings)
        secret = self._settings.n8n_webhook_secret.get_secret_value()
        if not re.fullmatch(r"[a-zA-Z0-9_-]{32,256}", secret):
            raise N8nUnavailable("n8n webhook authentication is not configured")
        request_id = uuid4()
        payload = {
            "event": "prediction_orchestration_requested",
            "request_id": str(request_id),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        request = urllib.request.Request(
            url,
            method="POST",
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json", "X-RMI-Orchestration-Key": secret},
        )
        opener = self._opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        try:
            with opener.open(
                request, timeout=self._settings.n8n_webhook_timeout_seconds
            ) as response:
                if response.status != 202:
                    raise ValueError
                data = response.read(65537)
                body = json.loads(data)
                if (
                    len(data) > 65536
                    or not isinstance(body, dict)
                    or set(body) != {"accepted"}
                    or body["accepted"] is not True
                ):
                    raise ValueError
        except (TimeoutError, urllib.error.URLError) as error:
            if isinstance(error, TimeoutError) or isinstance(
                getattr(error, "reason", None), TimeoutError
            ):
                raise N8nTimeout("n8n webhook deadline exceeded") from None
            raise N8nUnavailable("n8n webhook unavailable") from None
        except Exception:
            raise N8nUnavailable("n8n webhook unavailable") from None
        return WebhookAcknowledgement(accepted=True, request_id=request_id)
