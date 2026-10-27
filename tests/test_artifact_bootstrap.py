import gzip
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.artifact_bootstrap import FILES, BootstrapError, Source, bootstrap


def archive_bytes(files, extra=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        if extra:
            archive.addfile(extra, io.BytesIO(b""))
    return output.getvalue()


@pytest.fixture
def delivery(tmp_path):
    files = {n: b"synthetic-not-deserialized" for n in FILES - {"checksums.json"}}
    files["checksums.json"] = json.dumps(
        {n: hashlib.sha256(v).hexdigest() for n, v in files.items()}
    ).encode()
    digest = hashlib.sha256(files["checksums.json"]).hexdigest()
    return files, digest, tmp_path / "published"


def opener_for(data, *, status=200, length=None, url="https://storage.example.org/model.tar.gz"):
    response = Mock()
    response.status, response.geturl.return_value = status, url
    response.headers = {} if length is None else {"Content-Length": str(length)}
    response.read1.side_effect = io.BytesIO(data).read1
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    return opener


def deliver(delivery, data=None, source=None, opener=None):
    files, digest, destination = delivery
    return bootstrap(
        source or Source("https://storage.example.org/model.tar.gz", "storage.example.org"),
        destination,
        root=destination.parent,
        digest=digest,
        opener=opener or opener_for(data if data is not None else archive_bytes(files)),
    )


def test_disabled_makes_no_network_or_files(delivery):
    _, digest, destination = delivery
    network = Mock()
    assert (
        bootstrap(None, destination, root=destination.parent, digest=digest, opener=network)
        is False
    )
    network.open.assert_not_called()
    assert list(destination.parent.iterdir()) == []


@pytest.mark.parametrize(
    "url,host",
    [
        ("http://storage.example.org/model", "storage.example.org"),
        ("https://evil.example.org/model", "storage.example.org"),
        ("https://user:secret@storage.example.org/model", "storage.example.org"),
        ("https://127.0.0.1/model", "127.0.0.1"),
        ("https://storage.example.org:444/model", "storage.example.org"),
        ("https://storage.example.org/model#x", "storage.example.org"),
    ],
)
def test_source_rejected_before_network(delivery, url, host):
    network = Mock()
    with pytest.raises(BootstrapError):
        deliver(delivery, source=Source(url, host), opener=network)
    network.open.assert_not_called()


def test_verified_atomic_publish_without_deserialization(delivery, monkeypatch):
    files, _, destination = delivery
    import joblib

    decoder = Mock(side_effect=AssertionError("must not deserialize"))
    monkeypatch.setattr(joblib, "load", decoder)
    original = Path.rename
    published = []

    def inspect(path, target):
        assert not target.exists()
        assert {p.name for p in path.iterdir()} == FILES
        assert all((path / n).read_bytes() == value for n, value in files.items())
        published.append(True)
        return original(path, target)

    monkeypatch.setattr(Path, "rename", inspect)
    assert deliver(delivery)
    assert published and {p.name for p in destination.iterdir()} == FILES
    if os.name != "nt":
        assert destination.stat().st_mode & 0o222 == 0
        assert all(p.stat().st_mode & 0o222 == 0 for p in destination.iterdir())
    decoder.assert_not_called()
    # Make pytest's temporary fixture removable on Windows too.
    destination.chmod(0o700)
    for p in destination.iterdir():
        p.chmod(0o600)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("/absolute", tarfile.REGTYPE),
        ("C:\\escape", tarfile.REGTYPE),
        ("unexpected", tarfile.REGTYPE),
        ("pipeline.joblib", tarfile.SYMTYPE),
        ("pipeline.joblib", tarfile.LNKTYPE),
        ("pipeline.joblib", tarfile.CHRTYPE),
        ("pipeline.joblib", tarfile.DIRTYPE),
        ("pipeline.joblib", tarfile.REGTYPE),
    ],
)
def test_reject_paths_links_devices_duplicates_and_cleanup(delivery, name, kind):
    files, _, destination = delivery
    member = tarfile.TarInfo(name)
    member.type = kind
    if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
        member.linkname = "outside"
    if kind != tarfile.REGTYPE and name in files:
        files.pop(name)  # Test file type rejection independently of duplicate-name rejection.
    with pytest.raises(BootstrapError):
        deliver(delivery, archive_bytes(files, member))
    assert list(destination.parent.iterdir()) == []


@pytest.mark.parametrize(
    "failure",
    [
        "hash",
        "manifest",
        "missing",
        "compressed",
        "expanded",
        "timeout",
        "redirect",
        "partial",
        "announced_size",
    ],
)
def test_delivery_failures_closed_and_sanitized(delivery, failure):
    files, digest, destination = delivery
    source = Source(
        "https://storage.example.org/model.tar.gz?private-query",
        "storage.example.org",
        authorization="private-credential",
    )
    if failure == "hash":
        files["pipeline.joblib"] = b"replacement"
    if failure == "manifest":
        delivery = files, "0" * 64, destination
    if failure == "missing":
        files.pop("contract.json")
    data = archive_bytes(files)
    opener = opener_for(data, url=source.url)
    if failure == "compressed":
        source = Source(source.url, source.allowed_host, max_bytes=10)
    if failure == "expanded":
        data = gzip.compress(b"A" * 100000)
        source = Source(source.url, source.allowed_host, max_bytes=4096)
        opener = opener_for(data, url=source.url)
    if failure == "timeout":
        opener.open.side_effect = TimeoutError("private-query private-credential")
    if failure == "redirect":
        opener = opener_for(data, status=302, url=source.url)
    if failure == "partial":
        opener.open.return_value.read1.side_effect = [b"partial", OSError("private-query")]
    if failure == "announced_size":
        opener.open.return_value.headers = {"Content-Length": str(100000000)}
    with pytest.raises(BootstrapError) as error:
        deliver(delivery, data, source, opener)
    assert str(error.value) == "Model artifact bootstrap failed"
    assert list(destination.parent.iterdir()) == []
    assert "private" not in repr(source)


def test_existing_destination_is_not_replaced(delivery):
    _, _, destination = delivery
    destination.mkdir()
    (destination / "marker").write_text("keep", encoding="utf-8")
    with pytest.raises(BootstrapError):
        deliver(delivery)
    assert (destination / "marker").read_text(encoding="utf-8") == "keep"


def test_content_length_success_does_not_read_closed_socket(delivery):
    data = archive_bytes(delivery[0])
    opener = opener_for(data, length=len(data))
    assert deliver(delivery, opener=opener)
    assert opener.open.return_value.read1.call_count == 1
    delivery[2].chmod(0o700)
    for p in delivery[2].iterdir():
        p.chmod(0o600)


def test_extracted_payload_budget_even_with_small_compressed_archive(delivery):
    files, digest, destination = delivery
    files["pipeline.joblib"] = b"A" * 3000
    files["metadata.json"] = b"B" * 3000
    data = archive_bytes(files)
    assert len(data) < 4096
    with pytest.raises(BootstrapError):
        deliver(
            (files, digest, destination),
            data,
            Source(
                "https://storage.example.org/model.tar.gz", "storage.example.org", max_bytes=4096
            ),
        )
    assert not destination.exists()


def test_total_download_deadline_and_cleanup(delivery):
    _, digest, destination = delivery
    opener = opener_for(archive_bytes(delivery[0]))
    times = iter([0, 61])
    with pytest.raises(BootstrapError):
        bootstrap(
            Source("https://storage.example.org/model.tar.gz", "storage.example.org"),
            destination,
            root=destination.parent,
            digest=digest,
            opener=opener,
            clock=lambda: next(times),
        )
    assert list(destination.parent.iterdir()) == []


def test_archive_pax_and_invalid_authorization_rejected(delivery):
    from app.core.artifact_bootstrap import NoRedirect

    assert NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.org") is None
    source = Source(
        "https://storage.example.org/model.tar.gz",
        "storage.example.org",
        authorization="secret\r\nInjected: value",
    )
    with pytest.raises(BootstrapError):
        source.validate()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name, content in delivery[0].items():
            info = tarfile.TarInfo(name)
            info.size, info.pax_headers = len(content), {"comment": "unapproved"}
            archive.addfile(info, io.BytesIO(content))
    with pytest.raises(BootstrapError):
        deliver(delivery, output.getvalue())


def test_runtime_failure_leaves_readiness_false_and_never_loads(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.main import create_app

    loader = Mock()
    monkeypatch.setattr("app.main.ModelService", loader)
    cfg = Settings(
        _env_file=None,
        environment="test",
        model_bootstrap_enabled=True,
        model_artifact_path=tmp_path / "published",
        model_artifact_root=tmp_path,
        model_artifact_manifest_sha256="0" * 64,
        model_artifact_source_url="http://untrusted.example.org/source",
        model_artifact_source_host="untrusted.example.org",
    )
    with TestClient(create_app(cfg)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
    loader.assert_not_called()


def test_reparse_parent_rejected_before_download(delivery, monkeypatch):
    _, _, destination = delivery
    original = Path.lstat

    def attributes(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        return (
            SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            if path == destination.parent
            else info
        )

    monkeypatch.setattr(Path, "lstat", attributes)
    network = Mock()
    with pytest.raises(BootstrapError):
        deliver(delivery, opener=network)
    network.open.assert_not_called()
