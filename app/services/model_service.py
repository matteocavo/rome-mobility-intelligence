from pathlib import Path

from app.ml.artifacts import load, probabilities


class ModelService:
    def __init__(self, artifact_path: Path):
        self.pipeline, self.metadata = load(artifact_path)

    @property
    def threshold(self) -> float:
        return self.metadata.threshold

    def predict_proba(self, features):
        return probabilities(self.pipeline, features)

    def predict(self, features):
        return (self.predict_proba(features) >= self.threshold).astype(int)

    def info(self):
        return self.metadata.model_dump(
            include={
                "model_type",
                "trained_at",
                "feature_contract_version",
                "feature_contract_hash",
                "threshold",
                "decision_rule",
                "validation_metrics",
                "test_metrics",
                "synthetic",
            }
        )
