"""Provider-neutral startup policy. Failure messages never interpolate private config."""

import re
from ipaddress import ip_network
from urllib.parse import urlsplit

from app.core.config import Settings
from app.core.service_auth import valid_service_configuration
from app.core.workload_auth import WorkloadCredentials


def validate_deployment(cfg: Settings):
    try:
        if len(cfg.public_trusted_proxy_cidrs) > 16:
            raise ValueError
        if bool(cfg.public_trusted_proxy_cidrs) != (cfg.public_client_ip_header != "none"):
            raise ValueError
        for value in cfg.public_trusted_proxy_cidrs:
            network = ip_network(value, strict=True)
            if network.prefixlen == 0:
                raise ValueError
        if not cfg.allowed_hosts or any(
            not host or any(c in host for c in "*/@\\ \t\r\n") or host != host.lower()
            for host in cfg.allowed_hosts
        ):
            raise ValueError
        for origin in cfg.cors_allowed_origins:
            url = urlsplit(origin)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
                or url.path
                or url.query
                or url.fragment
                or "*" in origin
            ):
                raise ValueError
            if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError
        if cfg.n8n_service_api_key.get_secret_value() and not valid_service_configuration(cfg):
            raise ValueError
        if cfg.environment == "production":
            if not valid_service_configuration(cfg):
                raise ValueError
            if any(
                not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,}", h)
                or h.endswith((".invalid", ".localhost", ".local", ".internal"))
                for h in cfg.allowed_hosts
            ):
                raise ValueError
            if any(urlsplit(o).scheme != "https" for o in cfg.cors_allowed_origins):
                raise ValueError
            if (
                not cfg.model_artifact_path
                or not cfg.model_artifact_path.is_absolute()
                or not cfg.model_artifact_root
                or not cfg.model_artifact_root.is_absolute()
                or not re.fullmatch(r"[a-f0-9]{64}", cfg.model_artifact_manifest_sha256)
            ):
                raise ValueError
            WorkloadCredentials(cfg)  # Configuration only; no dependency network probes.
            if cfg.databricks_credential_target:
                raise ValueError  # A production service cannot read the operator's Windows store.
            if cfg.database_url.get_secret_value():
                from sqlalchemy.engine import make_url

                database = make_url(cfg.database_url.get_secret_value())
                if (
                    database.drivername not in {"postgresql", "postgresql+psycopg"}
                    or database.query.get("sslmode") != "verify-full"
                ):
                    raise ValueError
            elif cfg.enable_prediction_persistence:
                raise ValueError
    except Exception:
        raise RuntimeError("Deployment configuration is invalid or incomplete") from None
