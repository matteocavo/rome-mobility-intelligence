"""Immutable, private, trusted-local cache; data files must remain outside Git."""

import hashlib
import json
from pathlib import Path

import joblib

from app.contracts.operational_ml import HASH
from app.data.training_repository import validate_labeled


def load_export(path: Path, *, config: dict, seed: int, code_sha: str):
    reference = json.loads((path / "export-manifest.json").read_text(encoding="utf-8"))
    cache = path / "partitions.joblib"
    if hashlib.sha256(cache.read_bytes()).hexdigest() != reference["cached_export_sha256"]:
        raise ValueError("Export cache checksum mismatch")
    if (
        reference["version"] != config["version"]
        or reference["temporal_plan"] != config["temporal_plan"]
        or reference["seed"] != seed
        or reference["feature_contract_hash"] != HASH
        or reference["trained_code_sha"] != code_sha
    ):
        raise ValueError("Cached export protocol differs from frozen configuration")
    partitions = joblib.load(cache)
    if set(partitions) != {"train", "validation", "test"}:
        raise ValueError("Incomplete cached export")
    for name, frame in partitions.items():
        validate_labeled(frame)
        if len(frame) != reference["partitions"][name]["exported_rows"]:
            raise ValueError("Cached row count mismatch")
    return partitions, reference
