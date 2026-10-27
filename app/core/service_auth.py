"""Dedicated inbound service credential; distinct from the outbound n8n webhook secret."""

import hmac
import re
from typing import Annotated

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.core.config import Settings

SERVICE_HEADER = "X-RMI-Service-Key"
PROTECTED_PATHS = frozenset(
    {
        "/predict",
        "/predict/batch",
        "/predictions/current",
        "/predictions/current/persist",
        "/predictions/history",
        "/model/info",
    }
)
scheme = APIKeyHeader(name=SERVICE_HEADER, scheme_name="ServiceKey", auto_error=False)


class ServiceAuthError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(
            "Service unavailable" if status == 503 else "Service authentication required"
        )


def valid_service_configuration(cfg: Settings) -> bool:
    key = cfg.n8n_service_api_key.get_secret_value()
    webhook = cfg.n8n_webhook_secret.get_secret_value()
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]{32,256}", key)) and (
        not webhook or not hmac.compare_digest(key.encode(), webhook.encode())
    )


def verify_service_key(cfg: Settings, provided: str | None):
    if not valid_service_configuration(cfg):
        raise ServiceAuthError(503)
    if (
        not provided
        or len(provided) > 256
        or not hmac.compare_digest(
            provided.encode(), cfg.n8n_service_api_key.get_secret_value().encode()
        )
    ):
        raise ServiceAuthError(401)


def require_service_key(request: Request, key: Annotated[str | None, Security(scheme)]):
    # Middleware authenticates before reading the body; dependency declares the OpenAPI boundary.
    if request.scope.get("state", {}).get("service_authenticated"):
        return
    try:
        verify_service_key(request.app.state.settings, key)
    except ServiceAuthError as error:
        raise HTTPException(error.status, str(error)) from None
