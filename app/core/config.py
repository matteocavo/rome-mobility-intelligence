from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    databricks_server_hostname: str = ""
    databricks_http_path: str = ""
    databricks_token: SecretStr = SecretStr("")
    databricks_client_id: str = ""
    databricks_client_secret: SecretStr = SecretStr("")
    databricks_credential_target: str = ""
    databricks_catalog: str = "rome_transport"
    databricks_schema: str = "features"
    training_table: str = "next_stop_delay_labeled"
    inference_table: str = "next_stop_delay_scoring"
    model_artifact_path: Path | None = None
    model_artifact_root: Path | None = None
    model_artifact_manifest_sha256: str = ""
    model_bootstrap_enabled: bool = False
    model_artifact_source_url: SecretStr = SecretStr("")
    model_artifact_source_host: str = ""
    model_artifact_source_auth: SecretStr = SecretStr("")
    model_artifact_max_bytes: int = Field(default=33554432, ge=1, le=33554432)
    model_artifact_download_timeout_seconds: float = Field(default=60, gt=0, le=120)
    databricks_query_timeout_seconds: float = Field(default=120, ge=0.05, le=600)
    databricks_queue_timeout_seconds: float = Field(default=1, ge=0, le=10)
    databricks_max_concurrent_queries: int = Field(default=1, ge=1, le=4)
    inference_max_batch_rows: int = Field(default=100, ge=1, le=100)
    inference_max_bytes: int = Field(default=8_000_000, ge=1024, le=64_000_000)
    database_url: SecretStr = SecretStr("")
    enable_prediction_persistence: bool = False
    database_pool_size: int = Field(default=2, ge=1, le=4)
    database_pool_timeout_seconds: int = Field(default=3, ge=1, le=10)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=15)
    database_statement_timeout_ms: int = Field(default=5000, ge=100, le=30000)
    history_max_rows: int = Field(default=200, ge=1, le=200)
    history_max_range_days: int = Field(default=7, ge=1, le=7)
    n8n_webhook_url: SecretStr = SecretStr("")
    n8n_webhook_secret: SecretStr = SecretStr("")
    n8n_webhook_allowed_host: str = ""
    n8n_webhook_timeout_seconds: float = Field(default=5, ge=0.1, le=10)
    n8n_service_api_key: SecretStr = SecretStr("")
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "::1", "testserver"]
    cors_allowed_origins: list[str] = []
    request_max_bytes: int = Field(default=262144, ge=1024, le=1048576)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_inference: int = Field(default=10, ge=1, le=1000)
    rate_limit_write: int = Field(default=2, ge=1, le=1000)
    rate_limit_read: int = Field(default=60, ge=1, le=1000)

    @field_validator("model_artifact_path", mode="before")
    @classmethod
    def empty_artifact_is_unconfigured(cls, value):
        return None if value == "" else value
