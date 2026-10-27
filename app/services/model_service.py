from pathlib import Path
from threading import Lock

import pandas as pd

from app.contracts.operational_ml import FEATURES, HASH, verify_contract
from app.ml.artifacts import load, probabilities
from app.ml.preprocessing import FeatureValidator


class ModelService:
    def __init__(self, artifact_path: Path, *, trusted_root: Path, expected_manifest_sha256: str):
        self.pipeline, self.metadata = load(
            artifact_path,
            trusted_root=trusted_root,
            expected_manifest_sha256=expected_manifest_sha256,
        )
        verify_contract()
        if self.metadata.feature_contract_hash != HASH:
            raise ValueError("Model contract mismatch")
        self._inference_lock = Lock()
        self.model_version = expected_manifest_sha256

    @property
    def threshold(self) -> float:
        return self.metadata.threshold

    def predict_proba(self, features):
        validated = FeatureValidator().transform(features)
        # Validation above does not replace raw inputs: the pipeline owns preprocessing.
        if tuple(validated.columns) != FEATURES:
            raise ValueError("Invalid feature order")
        with self._inference_lock:
            return probabilities(self.pipeline, features.loc[:, list(FEATURES)])

    def identity(self):
        return {
            "model_version": self.model_version,
            "feature_contract_hash": self.metadata.feature_contract_hash,
            "threshold": self.threshold,
        }

    def predict_batch(self, rows):
        frame = pd.DataFrame(rows)
        values = self.predict_proba(frame)
        return [
            {
                "major_delay_probability": float(value),
                "predicted_major_delay": bool(value >= self.threshold),
            }
            for value in values
        ]

    def predict_one(self, row):
        return self.predict_batch([row])[0]

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
                if key
                in {
                    "source_rows",
                    "purged_rows",
                    "unexpected_rejected_rows",
                    "eligible_rows",
                    "eligible_positives",
                    "exported_rows",
                    "positive_rate",
                    "snapshots",
                    "min_feed",
                    "max_feed",
                    "selected_keys_sha256",
                    "inclusion_weights",
                    "evaluation_sampling",
                    "evaluation_inclusion_probability",
                }
            }
            for name, entry in reference.get("partitions", {}).items()
        }
        result.update(self.identity())
        result.update(serving_status="ready", artifact_integrity_verified=True)
        return result
