import json
import os
import subprocess
import sys

import numpy as np
import pytest

from app.contracts.operational_ml import FEATURES
from app.ml.artifacts import load, probabilities
from app.services.model_service import ModelService


def test_roundtrip_new_python_process(bundle, frame, trained, tmp_path):
    features = frame.iloc[:12][list(FEATURES)].copy()
    features["route_id"] = "new-route-after-reload"
    features["agency_id"] = None
    expected = probabilities(trained[0], features)
    input_path, output_path = tmp_path / "input.json", tmp_path / "output.json"
    features.to_json(input_path, orient="split", double_precision=15)
    code = (
        "import json,sys,pandas as pd; from pathlib import Path; "
        "from app.ml.artifacts import load,probabilities; "
        "m,_=load(Path(sys.argv[1])); x=pd.read_json(sys.argv[2],orient='split'); "
        "Path(sys.argv[3]).write_text(json.dumps(probabilities(m,x).tolist()))"
    )
    subprocess.run(
        [sys.executable, "-c", code, str(bundle), str(input_path), str(output_path)],
        check=True,
        env={**os.environ, "OMP_NUM_THREADS": "1"},
    )
    np.testing.assert_allclose(
        expected, json.loads(output_path.read_text()), rtol=1e-12, atol=1e-12
    )


def test_artifact_metadata_and_saved_threshold(bundle, frame):
    service = ModelService(bundle)
    p = service.predict_proba(frame[list(FEATURES)])
    np.testing.assert_array_equal(service.predict(frame[list(FEATURES)]), p >= service.threshold)
    assert service.info()["synthetic"] is True


@pytest.mark.parametrize("file", ["pipeline.joblib", "metadata.json", "contract.json"])
def test_corrupt_bundle_rejected(bundle, file):
    with (bundle / file).open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="checksum"):
        load(bundle)


@pytest.mark.parametrize("change", ["threshold", "hash", "version"])
def test_semantic_metadata_validation_after_checksum(bundle, change):
    import hashlib

    data = json.loads((bundle / "metadata.json").read_text())
    if change == "threshold":
        data["threshold"] = 1.5
    elif change == "hash":
        data["feature_contract_hash"] = "wrong"
    else:
        data["sklearn_version"] = "0.0.invalid"
    (bundle / "metadata.json").write_text(json.dumps(data))
    manifest = json.loads((bundle / "checksums.json").read_text())
    manifest["metadata.json"] = hashlib.sha256((bundle / "metadata.json").read_bytes()).hexdigest()
    (bundle / "checksums.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load(bundle)


def test_validation_cli_smoke_and_invalid_exit(bundle, tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.validate_model_artifact", str(bundle)],
        capture_output=True,
        text=True,
        env={**os.environ, "OMP_NUM_THREADS": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"
    failure = subprocess.run(
        [sys.executable, "-m", "scripts.validate_model_artifact", str(tmp_path / "missing")],
        capture_output=True,
        text=True,
    )
    assert failure.returncode != 0


def test_candidate_comparison_and_threshold_metadata_serialization(trained):
    from app.contracts.schemas import ArtifactMetadata

    _, metadata = trained
    restored = ArtifactMetadata.model_validate_json(metadata.model_dump_json())
    assert restored.candidate_validation == metadata.candidate_validation
    for row in restored.threshold_grid:
        assert {
            "threshold",
            "precision",
            "recall",
            "f1",
            "predicted_positive_rate",
            "tp",
            "fp",
            "tn",
            "fn",
        } == set(row)
