"""Pinned upstream contract; Spark settings are provenance, not sklearn instructions."""

import hashlib
import json
from pathlib import Path

CORE_SHA = "7d263629b533f57af46ffaadcb56e4fcc0f296a7"
CONTRACT = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
NUMERIC = tuple(CONTRACT["numerical_features"])
CATEGORICAL = tuple(CONTRACT["categorical_features"])
FEATURES = NUMERIC + CATEGORICAL
HASH = "11682b3cc1ab5c1d8440af4f6294e932e815126c3dd86ab609f4d5f8f35c41a5"
LABEL = CONTRACT["target"]["label_column"]
DELAY = CONTRACT["target"]["delay_column"]
KEY = tuple(CONTRACT["observation_key"])


def verify_contract() -> None:
    if len(NUMERIC) != 42 or len(CATEGORICAL) != 5 or len(set(FEATURES)) != 47:
        raise ValueError("Invalid raw feature contract")
    if "trip_progress_ratio" in FEATURES or CONTRACT["feature_contract_hash"] != HASH:
        raise ValueError("Unexpected contract provenance")
    # Canonical upstream hash includes historical preprocessing; do not rehash only names.


def contract_digest() -> str:
    return hashlib.sha256(
        json.dumps(CONTRACT, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


verify_contract()
