from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.operational_ml import HASH


class ArtifactMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_version: Literal[1] = 1
    model_type: Literal["logistic_regression", "hist_gradient_boosting"]
    trained_at: str
    feature_contract_version: Literal[1] = 1
    feature_contract_hash: Literal[
        "11682b3cc1ab5c1d8440af4f6294e932e815126c3dd86ab609f4d5f8f35c41a5"
    ] = HASH
    contract_digest: str
    threshold: float = Field(gt=0, lt=1)
    decision_rule: Literal["probability >= threshold"] = "probability >= threshold"
    sklearn_version: str
    trained_code_sha: str
    training_data_reference: dict[str, Any]
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any]
    candidate_validation: dict[str, Any]
    threshold_grid: list[dict[str, float]]
    synthetic: bool

    @model_validator(mode="after")
    def require_provenance(self):
        if not self.training_data_reference or not self.trained_code_sha:
            raise ValueError("Training provenance required")
        return self
