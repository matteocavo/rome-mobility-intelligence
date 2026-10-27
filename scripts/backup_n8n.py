"""Operator-invoked encrypted n8n backup, never an application-data connection."""

import argparse
import io
import json
import os
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def archive(data: Path, deployment_config: Path, stream):
    """Caller must stop n8n. SQLite backup includes WAL; root encryption key is omitted."""
    for item in [data, deployment_config, *data.rglob("*")]:
        if item.is_symlink() or getattr(item.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Links are forbidden in backup")
        if not item.is_dir() and (not item.is_file() or item.stat().st_nlink != 1):
            raise ValueError("Only regular backup files are allowed")
    # Deployment config is an allowlisted nonsecret .env-style file, not arbitrary env.
    allowed = {
        "N8N_HOST",
        "ACME_EMAIL",
        "N8N_DATA_DIR",
        "CADDY_DATA_DIR",
        "CADDY_CONFIG_DIR",
        "N8N_ENCRYPTION_KEY_FILE",
    }
    lines = deployment_config.read_text(encoding="utf-8").splitlines()
    if any(
        line.strip() and not line.lstrip().startswith("#") and line.split("=", 1)[0] not in allowed
        for line in lines
    ):
        raise ValueError("Deployment configuration contains unexpected fields")
    with tempfile.TemporaryDirectory(prefix="n8n-backup-") as folder:
        snapshot = Path(folder) / "database.sqlite"
        with closing(
            sqlite3.connect((data / "database.sqlite").as_uri() + "?mode=ro", uri=True)
        ) as src:
            with closing(sqlite3.connect(snapshot)) as dst:
                src.backup(dst)
        with tarfile.open(fileobj=stream, mode="w|gz", format=tarfile.USTAR_FORMAT) as tar:
            for path in sorted(data.rglob("*")):
                relative = path.relative_to(data).as_posix()
                if path.is_dir() or relative in {
                    "database.sqlite",
                    "database.sqlite-wal",
                    "database.sqlite-shm",
                    "database.sqlite-journal",
                    "config",
                }:
                    continue
                tar.add(path, arcname="n8n/" + relative, recursive=False)
            tar.add(snapshot, arcname="n8n/database.sqlite", recursive=False)
            if (data / "config").exists():
                config = json.loads((data / "config").read_text(encoding="utf-8"))
                config.pop("encryptionKey", None)
                # Not named config: n8n must recreate its config using the separately
                # restored encryption key before startup, not read an incomplete file.
                raw = json.dumps(config).encode()
                info = tarfile.TarInfo("nonsecret-instance-settings.json")
                info.size, info.mode = len(raw), 0o600
                tar.addfile(info, io.BytesIO(raw))
            tar.add(deployment_config, arcname="deployment.env", recursive=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--passphrase-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    partial = None
    try:
        if os.name != "posix":
            raise ValueError("Linux operator tool")
        for path in (args.data_dir, args.env_file, args.passphrase_file, args.output):
            if not path.is_absolute() or path.resolve().is_relative_to(ROOT) or ".." in path.parts:
                raise ValueError("Backup paths must be absolute and outside Git")
        mode = args.passphrase_file.stat().st_mode
        if mode & 0o077 or not stat.S_ISREG(mode) or args.passphrase_file.stat().st_size < 16:
            raise ValueError("Private passphrase file required")
        compose = ROOT / "ops/n8n/oci/compose.yaml"
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(args.env_file),
                "-f",
                str(compose),
                "ps",
                "--status",
                "running",
                "--quiet",
                "n8n",
            ],
            check=True,
            capture_output=True,
        )
        if result.stdout.strip() or args.output.exists() or args.output.suffix != ".gpg":
            raise ValueError("Stop n8n and choose a new encrypted output")
        if args.output.parent.stat().st_mode & 0o077:
            raise ValueError("Private output directory required")
        fd, name = tempfile.mkstemp(prefix=".n8n-backup-", dir=args.output.parent)
        os.close(fd)
        partial = Path(name)
        with subprocess.Popen(
            [
                "gpg",
                "--batch",
                "--yes",
                "--pinentry-mode",
                "loopback",
                "--passphrase-file",
                str(args.passphrase_file),
                "--symmetric",
                "--cipher-algo",
                "AES256",
                "--output",
                str(partial),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as process:
            try:
                archive(args.data_dir, args.env_file, process.stdin)
            except Exception:
                process.kill()
                raise
            finally:
                process.stdin.close()
            if process.wait(timeout=60) != 0:
                raise ValueError("Encryption failed")
        partial.rename(args.output)
        partial = None
        print("Encrypted n8n backup complete; encryption key must be backed up separately")
    except Exception:
        raise SystemExit("n8n backup failed; diagnostics suppressed") from None
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
