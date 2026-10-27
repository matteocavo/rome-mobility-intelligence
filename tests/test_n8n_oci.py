import io
import json
import os
import shutil
import sqlite3
import tarfile
from pathlib import Path

import pytest

from scripts import backup_n8n, validate_n8n_oci


def test_oci_config_pinned_arm64_private_storage_and_no_application_credentials():
    validate_n8n_oci.validate()
    lock = json.loads((validate_n8n_oci.ASSETS / "image-lock.json").read_text(encoding="utf-8"))
    assert len(lock["images"]) == 2
    assert "Docker Registry v2" in lock["method"]
    assert all(i["version"] != "latest" and i["linux_arm64_digest"] for i in lock["images"])


@pytest.mark.parametrize("mutation", ["port", "pin", "key", "database", "architecture"])
def test_oci_policy_rejects_unsafe_mutations(tmp_path, monkeypatch, mutation):
    assets = tmp_path / "oci"
    shutil.copytree(validate_n8n_oci.ASSETS, assets)
    path = assets / "compose.yaml"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "port": ('    user: "1000:1000"', '    ports: ["5678:5678"]\n    user: "1000:1000"'),
        "pin": ("n8nio/n8n:2.45.4@sha256:", "n8nio/n8n:latest@sha256:"),
        "key": (
            "N8N_ENCRYPTION_KEY_FILE: /run/secrets/n8n_encryption_key",
            "N8N_ENCRYPTION_KEY: literal",
        ),
        "database": ("DB_TYPE: sqlite", "DB_TYPE: postgresdb"),
        "architecture": ("platform: linux/arm64", "platform: linux/amd64"),
    }
    text = text.replace(*replacements[mutation])
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(validate_n8n_oci, "ASSETS", assets)
    with pytest.raises(AssertionError):
        validate_n8n_oci.validate()


def backup_fixture(tmp_path):
    data = tmp_path / "n8n"
    data.mkdir()
    with sqlite3.connect(data / "database.sqlite") as db:
        db.execute("create table workflow_entity (name text, active integer)")
        db.execute("insert into workflow_entity values ('synthetic-workflow',0)")
    (data / "config").write_text(
        json.dumps({"encryptionKey": "synthetic-private-key", "fsStorageMigrated": True}),
        encoding="utf-8",
    )
    (data / "workflow-state.txt").write_text("synthetic-state", encoding="utf-8")
    config = tmp_path / "deployment.env"
    config.write_text(
        "N8N_HOST=n8n.example.org\nN8N_ENCRYPTION_KEY_FILE=/external/key\n", encoding="utf-8"
    )
    return data, config


def test_backup_consistent_sqlite_and_external_key_not_archived(tmp_path):
    data, config = backup_fixture(tmp_path)
    output = io.BytesIO()
    backup_n8n.archive(data, config, output)
    output.seek(0)
    with tarfile.open(fileobj=output, mode="r:gz") as tar:
        assert "n8n/config" not in tar.getnames()
        settings = tar.extractfile("nonsecret-instance-settings.json").read()
        assert json.loads(settings) == {"fsStorageMigrated": True}
        assert b"synthetic-private-key" not in settings
        assert all(m.isfile() and not m.issym() and not m.islnk() for m in tar)
        restored = tmp_path / "restored.sqlite"
        restored.write_bytes(tar.extractfile("n8n/database.sqlite").read())
    with sqlite3.connect(restored) as db:
        assert db.execute("select * from workflow_entity").fetchall() == [("synthetic-workflow", 0)]
    assert "synthetic-private-key" in (data / "config").read_text(encoding="utf-8")


def test_backup_rejects_secret_configuration(tmp_path):
    data, config = backup_fixture(tmp_path)
    config.write_text("N8N_ENCRYPTION_KEY=synthetic-private-key", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected fields"):
        backup_n8n.archive(data, config, io.BytesIO())


@pytest.mark.skipif(os.name == "nt", reason="Linux deployment link policy")
def test_backup_rejects_link_to_external_secret(tmp_path):
    data, config = backup_fixture(tmp_path)
    (data / "external-link").symlink_to(config)
    with pytest.raises(ValueError, match="Links"):
        backup_n8n.archive(data, config, io.BytesIO())


def test_backup_cli_fails_sanitized_before_side_effects(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "backup_n8n",
            "--data-dir",
            ".",
            "--env-file",
            ".",
            "--passphrase-file",
            ".",
            "--output",
            ".",
        ],
    )
    with pytest.raises(SystemExit) as error:
        backup_n8n.main()
    assert str(error.value) == "n8n backup failed; diagnostics suppressed"
    assert not capsys.readouterr().out


def test_restore_runbook_unpublishes_before_server_and_backs_up_key_separately():
    text = (validate_n8n_oci.ASSETS / "BACKUP_RESTORE.md").read_text(encoding="utf-8")
    assert "unpublish:workflow --all" in text
    assert "N8N_ENCRYPTION_KEY separately" in text
    assert "no persistence test" in text
    assert "same pinned n8n version" in text
    assert not Path("ops/n8n/compose.yml").exists()
