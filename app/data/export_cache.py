"""Immutable, private, trusted-local cache; data files must remain outside Git."""

import hashlib
import io
import json
import re
from pathlib import Path

import joblib

from app.contracts.operational_ml import HASH
from app.core.trusted_files import trusted_bytes
from app.data.training_repository import validate_labeled


def load_export(path: Path, *, config: dict, seed: int, code_sha: str):
    expected = config.get("export_manifest_sha256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("An out-of-band export manifest checksum is required")
    manifest = trusted_bytes(path / "export-manifest.json", root=path, max_bytes=64_000_000)
    if hashlib.sha256(manifest).hexdigest() != expected:
        raise ValueError("External export manifest checksum mismatch")
    reference = json.loads(manifest)
    cache = path / "partitions.joblib"
    cached_bytes = trusted_bytes(cache, root=path, max_bytes=512_000_000)
    if hashlib.sha256(cached_bytes).hexdigest() != reference["cached_export_sha256"]:
        raise ValueError("Export cache checksum mismatch")
    if (
        reference["version"] != config["version"]
        or reference["temporal_plan"] != config["temporal_plan"]
        or reference["seed"] != seed
        or reference["feature_contract_hash"] != HASH
        or reference["trained_code_sha"] != code_sha
    ):
        raise ValueError("Cached export protocol differs from frozen configuration")
    partitions = joblib.load(io.BytesIO(cached_bytes))
    if set(partitions) != {"train", "validation", "test"}:
        raise ValueError("Incomplete cached export")
    for name, frame in partitions.items():
        validate_labeled(frame)
        if len(frame) != reference["partitions"][name]["exported_rows"]:
            raise ValueError("Cached row count mismatch")
    return partitions, reference
