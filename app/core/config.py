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
    databricks_query_timeout_seconds: float = Field(default=120, ge=0.05, le=600)
    databricks_queue_timeout_seconds: float = Field(default=1, ge=0, le=10)
    databricks_max_concurrent_queries: int = Field(default=1, ge=1, le=4)

    @field_validator("model_artifact_path", mode="before")
    @classmethod
    def empty_artifact_is_unconfigured(cls, value):
        return None if value == "" else value
