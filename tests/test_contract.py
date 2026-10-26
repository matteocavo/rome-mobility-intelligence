import json

import numpy as np
import pytest

from app.contracts.operational_ml import (
    CATEGORICAL,
    CONTRACT,
    FEATURES,
    HASH,
    NUMERIC,
    contract_digest,
    verify_contract,
)
from app.ml.preprocessing import FeatureValidator


def test_contract_counts_and_categories():
    verify_contract()
    assert len(FEATURES) == 47 and len(NUMERIC) == 42
    assert CATEGORICAL == ("route_id", "route_type", "direction_id", "agency_id", "current_status")
    assert "trip_progress_ratio" not in FEATURES
    assert CONTRACT["target"]["seconds"] == 300
    assert CONTRACT["training"]["validated_version"] == 12


def test_hash_and_serialized_provenance():
    assert HASH == "11682b3cc1ab5c1d8440af4f6294e932e815126c3dd86ab609f4d5f8f35c41a5"
    assert json.loads(json.dumps(CONTRACT))["feature_contract_hash"] == HASH
    assert len(contract_digest()) == 64


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "nonnumeric", "inf"])
def test_reject_invalid_features(frame, change):
    x = frame[list(FEATURES)].copy()
    if change == "missing":
        x = x.drop(columns=[FEATURES[0]])
    elif change == "extra":
        x["trip_progress_ratio"] = 0
    elif change == "duplicate":
        x.columns = [FEATURES[1], *FEATURES[1:]]
    elif change == "nonnumeric":
        x[FEATURES[0]] = "not-a-number"
    else:
        x.loc[0, FEATURES[0]] = np.inf
    with pytest.raises(ValueError):
        FeatureValidator().transform(x)


def test_names_define_order_and_numeric_strings_coerce(frame):
    x = frame[list(reversed(FEATURES))].copy()
    x[FEATURES[0]] = x[FEATURES[0]].astype(str)
    result = FeatureValidator().transform(x)
    assert tuple(result.columns) == FEATURES
    assert result[FEATURES[0]].dtype.kind == "f"
