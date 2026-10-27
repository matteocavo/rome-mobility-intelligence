import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ml.artifacts import load


def test_no_external_pin_never_deserializes(bundle, monkeypatch):
    from app.ml import artifacts

    decoder = MagicMock()
    monkeypatch.setattr(artifacts.joblib, "load", decoder)
    with pytest.raises(ValueError, match="external"):
        load(bundle, trusted_root=bundle.parent, expected_manifest_sha256="")
    decoder.assert_not_called()


def test_attacker_replaces_payload_and_internal_checksums(bundle, bundle_trust, monkeypatch):
    from app.ml import artifacts

    decoder = MagicMock()
    monkeypatch.setattr(artifacts.joblib, "load", decoder)
    malicious = b"attacker-controlled serialized model"
    (bundle / "pipeline.joblib").write_bytes(malicious)
    manifest = json.loads((bundle / "checksums.json").read_text())
    manifest["pipeline.joblib"] = hashlib.sha256(malicious).hexdigest()
    (bundle / "checksums.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="External manifest"):
        load(bundle, **bundle_trust)
    decoder.assert_not_called()


def test_deserializes_verified_memory_not_a_reopened_path(bundle, bundle_trust, monkeypatch):
    from app.ml import artifacts

    original = artifacts.joblib.load
    validated = (bundle / "pipeline.joblib").read_bytes()

    def inspect(stream):
        assert isinstance(stream, io.BytesIO)
        assert stream.getvalue() == validated
        # A post-verification replacement cannot change the bytes handed to joblib.
        (bundle / "pipeline.joblib").write_bytes(b"late replacement")
        return original(stream)

    monkeypatch.setattr(artifacts.joblib, "load", inspect)
    _, metadata = load(bundle, **bundle_trust)
    assert metadata.synthetic


def test_root_escape_rejected(bundle, bundle_trust):
    with pytest.raises(ValueError, match="outside"):
        load(
            bundle,
            trusted_root=bundle / "another-root",
            expected_manifest_sha256=bundle_trust["expected_manifest_sha256"],
        )


def test_parent_traversal_rejected(bundle, bundle_trust):
    traversal = bundle / ".." / bundle.name
    with pytest.raises(ValueError, match="traverse"):
        load(traversal, **bundle_trust)


def test_symlink_even_with_correct_bytes_rejected(bundle, bundle_trust, tmp_path):
    target = tmp_path / "external-model.joblib"
    (bundle / "pipeline.joblib").replace(target)
    try:
        (bundle / "pipeline.joblib").symlink_to(target)
    except OSError:
        pytest.skip("OS does not permit creating a symlink in this test account")
    with pytest.raises(ValueError, match="Symlink/reparse"):
        load(bundle, **bundle_trust)


def test_windows_reparse_attribute_rejected(bundle, bundle_trust, monkeypatch):
    original = Path.lstat

    def attributes(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path.name == "pipeline.joblib":
            return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400)
        return result

    monkeypatch.setattr(Path, "lstat", attributes)
    with pytest.raises(ValueError, match="Symlink/reparse"):
        load(bundle, **bundle_trust)


@pytest.mark.skipif(os.name == "nt", reason="POSIX write-bit policy; Windows deployment uses ACLs")
def test_group_world_writable_file_rejected(bundle, bundle_trust):
    (bundle / "pipeline.joblib").chmod(0o666)
    with pytest.raises(ValueError, match="writable"):
        load(bundle, **bundle_trust)
