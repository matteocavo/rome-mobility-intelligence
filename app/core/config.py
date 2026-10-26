from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    databricks_server_hostname: str = ""
    databricks_http_path: str = ""
    databricks_token: SecretStr = SecretStr("")
    databricks_catalog: str = "rome_transport"
    databricks_schema: str = "features"
    training_table: str = "next_stop_delay_labeled"
    inference_table: str = "next_stop_delay_scoring"
    model_artifact_path: Path | None = None

    @field_validator("model_artifact_path", mode="before")
    @classmethod
    def empty_artifact_is_unconfigured(cls, value):
        return None if value == "" else value
