import hashlib
import json
from dataclasses import asdict

import joblib
import pytest

from app.contracts.operational_ml import HASH
from app.data.export_cache import load_export
from app.data.training_repository import temporal_split
from app.ml.fixtures import FIXTURE_PLAN


@pytest.fixture
def export_cache(tmp_path, frame):
    joblib.dump(temporal_split(frame, FIXTURE_PLAN), tmp_path / "partitions.joblib")
    manifest = {
        "version": 12,
        "seed": 42,
        "temporal_plan": asdict(FIXTURE_PLAN),
        "feature_contract_hash": HASH,
        "trained_code_sha": "fixture-code",
        "cached_export_sha256": hashlib.sha256(
            (tmp_path / "partitions.joblib").read_bytes()
        ).hexdigest(),
        "partitions": {
            name: {"exported_rows": len(f)}
            for name, f in temporal_split(frame, FIXTURE_PLAN).items()
        },
    }
    (tmp_path / "export-manifest.json").write_text(json.dumps(manifest))
    return tmp_path, {
        "version": 12,
        "temporal_plan": asdict(FIXTURE_PLAN),
        "export_manifest_sha256": hashlib.sha256(
            (tmp_path / "export-manifest.json").read_bytes()
        ).hexdigest(),
    }


def test_load_exact_export_without_credentials(export_cache):
    path, config = export_cache
    partitions, reference = load_export(path, config=config, seed=42, code_sha="fixture-code")
    assert set(partitions) == {"train", "validation", "test"}
    assert reference["version"] == 12


@pytest.mark.parametrize("bad", ["checksum", "seed", "version", "code_sha"])
def test_cache_protocol_fail_closed(export_cache, bad):
    path, config = export_cache
    if bad == "checksum":
        with (path / "partitions.joblib").open("ab") as stream:
            stream.write(b"corrupted")
    if bad == "version":
        config["version"] = 13
    with pytest.raises(ValueError):
        load_export(
            path,
            config=config,
            seed=43 if bad == "seed" else 42,
            code_sha="wrong" if bad == "code_sha" else "fixture-code",
        )


def test_cache_requires_independent_manifest_pin(export_cache, monkeypatch):
    from unittest.mock import MagicMock

    from app.data import export_cache as module

    path, config = export_cache
    config.pop("export_manifest_sha256")
    decode = MagicMock()
    monkeypatch.setattr(module.joblib, "load", decode)
    with pytest.raises(ValueError, match="out-of-band"):
        load_export(path, config=config, seed=42, code_sha="fixture-code")
    decode.assert_not_called()


def test_recomputed_cache_and_manifest_cannot_replace_external_pin(export_cache, monkeypatch):
    from unittest.mock import MagicMock

    from app.data import export_cache as module

    path, config = export_cache
    (path / "partitions.joblib").write_bytes(b"untrusted replacement")
    manifest = json.loads((path / "export-manifest.json").read_text())
    manifest["cached_export_sha256"] = hashlib.sha256(
        (path / "partitions.joblib").read_bytes()
    ).hexdigest()
    (path / "export-manifest.json").write_text(json.dumps(manifest))
    decode = MagicMock()
    monkeypatch.setattr(module.joblib, "load", decode)
    with pytest.raises(ValueError, match="External"):
        load_export(path, config=config, seed=42, code_sha="fixture-code")
    decode.assert_not_called()
