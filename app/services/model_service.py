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
        result = self.metadata.model_dump(
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
                "training_data_reference",
            }
        )
        reference = self.metadata.training_data_reference
        result["training_data_reference"] = {
            key: reference[key]
            for key in (
                "source",
                "table",
                "version",
                "feature_contract_hash",
                "temporal_plan",
                "seed",
                "sampling_algorithm",
                "selected_candidate",
                "evaluation_status",
            )
            if key in reference
        }
        result["training_data_reference"]["partitions"] = {
            name: {
                key: value
                for key, value in entry.items()
                if key not in {"query", "parameters", "strata_allocation"}
            }
            for name, entry in reference.get("partitions", {}).items()
        }
        return result
