"""SQL-scoped OAuth M2M. No developer profile or personal-token fallback."""

import base64
import ctypes
import json
import logging
import re
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid

from app.core.config import Settings
from app.core.databricks_diagnostics import failure_category

logger = logging.getLogger(__name__)


class WorkloadAuthenticationError(RuntimeError):
    def __init__(self, message, category='databricks_configuration'):
        from app.core.databricks_diagnostics import CATEGORIES
        self.category = category if category in CATEGORIES else 'databricks_unknown'
        super().__init__(message)


def read_windows_secret(target: str, client_id: str) -> str:
    if sys.platform != "win32":
        raise WorkloadAuthenticationError("Windows credential storage is unavailable")
    from ctypes import wintypes

    class Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(Credential)),
    ]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    record = ctypes.POINTER(Credential)()
    if not api.CredReadW(target, 1, 0, ctypes.byref(record)):
        raise WorkloadAuthenticationError("Workload credential is unavailable in the local store")
    try:
        if record.contents.UserName != client_id:
            raise WorkloadAuthenticationError("Stored credential belongs to another workload")
        return ctypes.string_at(
            record.contents.CredentialBlob, record.contents.CredentialBlobSize
        ).decode("utf-8")
    finally:
        api.CredFree(record)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def exchange_token(host: str, client_id: str, secret: str) -> dict:
    credential = base64.b64encode((client_id + ":" + secret).encode()).decode()
    request = urllib.request.Request(
        "https://" + host + "/oidc/v1/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "sql"}).encode(),
        headers={
            "Authorization": "Basic " + credential,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        NoRedirect(),
    )
    try:
        with opener.open(request, timeout=15) as response:
            payload = response.read(65537)
            if len(payload) > 65536:
                raise ValueError("Oversized OAuth response")
            return json.loads(payload)
    except Exception as error:
        category = failure_category(error)
        logger.warning("databricks_failure stage=oauth category=%s", category)
        raise WorkloadAuthenticationError("Workload OAuth exchange failed", category) from None


class WorkloadCredentials:
    def __init__(self, settings: Settings):
        if settings.databricks_token.get_secret_value():
            raise WorkloadAuthenticationError(
                "Personal/access-token configuration is not supported"
            )
        if not re.fullmatch(
            r"[a-zA-Z0-9-]+\.cloud\.databricks\.com", settings.databricks_server_hostname
        ):
            raise WorkloadAuthenticationError(
                "A trusted AWS Databricks workspace hostname is required"
            )
        try:
            uuid.UUID(settings.databricks_client_id)
        except ValueError:
            raise WorkloadAuthenticationError("A workload client ID is required") from None
        sources = [
            bool(settings.databricks_client_secret.get_secret_value()),
            bool(settings.databricks_credential_target),
        ]
        if sum(sources) != 1:
            raise WorkloadAuthenticationError("Configure exactly one workload secret source")
        self._settings = settings
        self._token = ""
        self._expires = 0.0
        self._lock = threading.Lock()

    def __call__(self):
        # The SQL connector calls this once to obtain its renewable header factory.
        return self.headers

    def headers(self) -> dict[str, str]:
        with self._lock:
            if time.monotonic() >= self._expires:
                cfg = self._settings
                secret = cfg.databricks_client_secret.get_secret_value()
                if not secret:
                    secret = read_windows_secret(
                        cfg.databricks_credential_target, cfg.databricks_client_id
                    )
                try:
                    result = exchange_token(
                        cfg.databricks_server_hostname, cfg.databricks_client_id, secret
                    )
                    ttl = int(result["expires_in"])
                    if ttl <= 60 or set(result.get("scope", "").split()) != {"sql"}:
                        raise ValueError("Unexpected scope or expiry")
                    token = result["access_token"]
                    if not isinstance(token, str) or not token:
                        raise ValueError("Missing OAuth token")
                    self._token = token
                    self._expires = time.monotonic() + min(ttl, 3600) - 60
                except Exception:
                    raise WorkloadAuthenticationError("Invalid workload OAuth response") from None
            return {"Authorization": "Bearer " + self._token}
