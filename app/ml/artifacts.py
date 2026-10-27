"""Load only trusted local bundles: joblib is executable pickle, not an exchange format."""

import hashlib
import io
import json
import re
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.pipeline import Pipeline

from app.contracts.operational_ml import CONTRACT, FEATURES, contract_digest
from app.contracts.schemas import ArtifactMetadata
from app.core.trusted_files import trusted_bytes


def persist(path: Path, pipeline: Pipeline, metadata: ArtifactMetadata) -> None:
    path.mkdir(parents=True, exist_ok=False)
    # Failure leaves an invalid bundle; never silently replace an existing model.
    joblib.dump(pipeline, path / "pipeline.joblib")
    (path / "metadata.json").write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
    (path / "contract.json").write_text(json.dumps(CONTRACT, indent=2), encoding="utf-8")
    checksums = {
        name: hashlib.sha256((path / name).read_bytes()).hexdigest()
        for name in ("pipeline.joblib", "metadata.json", "contract.json")
    }
    (path / "checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")


def load(
    path: Path, *, trusted_root: Path, expected_manifest_sha256: str
) -> tuple[Pipeline, ArtifactMetadata]:
    if trusted_root is None or not re.fullmatch(r"[a-f0-9]{64}", expected_manifest_sha256):
        raise ValueError("An external trusted root and manifest digest are required")
    manifest = trusted_bytes(path / "checksums.json", root=trusted_root, max_bytes=65536)
    if hashlib.sha256(manifest).hexdigest() != expected_manifest_sha256:
        raise ValueError("External manifest checksum mismatch")
    checksums = json.loads(manifest)
    if set(checksums) != {"pipeline.joblib", "metadata.json", "contract.json"}:
        raise ValueError("Incomplete artifact manifest")
    payloads = {}
    for name, checksum in checksums.items():
        if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
            raise ValueError("Invalid artifact checksum")
        payloads[name] = trusted_bytes(path / name, root=trusted_root, max_bytes=64_000_000)
        if hashlib.sha256(payloads[name]).hexdigest() != checksum:
            raise ValueError("Artifact checksum mismatch")
    metadata = ArtifactMetadata.model_validate_json(payloads["metadata.json"])
    if metadata.contract_digest != contract_digest():
        raise ValueError("Contract mismatch")
    if json.loads(payloads["contract.json"]) != CONTRACT:
        raise ValueError("Unexpected full feature contract")
    if metadata.sklearn_version != sklearn.__version__:
        raise ValueError("Use the exact training sklearn version to reload")
    # Deserialize exactly the bytes already checked, never reopen the path (TOCTOU).
    pipeline = joblib.load(io.BytesIO(payloads["pipeline.joblib"]))
    if not isinstance(pipeline, Pipeline) or tuple(pipeline.feature_names_in_) != FEATURES:
        raise ValueError("Invalid pipeline feature names")
    if list(pipeline.classes_) != [0, 1]:
        raise ValueError("Invalid class order")
    actual = type(pipeline.named_steps["classifier"]).__name__
    expected = {
        "logistic_regression": "LogisticRegression",
        "hist_gradient_boosting": "HistGradientBoostingClassifier",
    }
    if actual != expected[metadata.model_type]:
        raise ValueError("Model metadata mismatch")
    return pipeline, metadata


def probabilities(pipeline, features):
    result = pipeline.predict_proba(features)
    if not np.isfinite(result).all() or ((result < 0) | (result > 1)).any():
        raise ValueError("Invalid model probabilities")
    if result.shape != (len(features), 2) or not np.allclose(result.sum(axis=1), 1):
        raise ValueError("Invalid probability shape or sum")
    return result[:, 1]
