"""Static policy, optional offline ARM64 import/Compose smoke; never provision OCI."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "ops/n8n/oci"


def validate():
    compose = (ASSETS / "compose.yaml").read_text(encoding="utf-8")
    images = json.loads((ASSETS / "image-lock.json").read_text(encoding="utf-8"))["images"]
    pins = re.findall(r"image: (\S+)", compose)
    assert len(pins) == 2 and compose.count("platform: linux/arm64") == 2
    for image in images:
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", image["linux_arm64_digest"])
        name = image["repository"].removeprefix("library/")
        assert f"{name}:{image['version']}@{image['index_digest']}" in pins
    n8n = compose.split("  caddy:")[0]
    assert "ports:" not in n8n and "target: /home/node/.n8n" in n8n
    assert 'user: "1000:1000"' in n8n and "create_host_path: false" in n8n
    assert "N8N_ENCRYPTION_KEY_FILE: /run/secrets/n8n_encryption_key" in n8n
    assert "${N8N_ENCRYPTION_KEY_FILE:?" in compose
    assert 'N8N_PROXY_HOPS: "1"' in n8n and "N8N_PROTOCOL: https" in n8n
    assert 'N8N_SECURE_COOKIE: "true"' in n8n
    assert "DB_TYPE: sqlite" in n8n
    assert "EXECUTIONS_DATA_SAVE_ON_SUCCESS: none" in n8n
    assert "EXECUTIONS_DATA_SAVE_ON_ERROR: none" in n8n
    assert 'EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS: "false"' in n8n
    assert not re.search(
        r"(?i)postgres|databricks|service.api.key|docker.sock|privileged:", compose
    )
    caddy = (ASSETS / "Caddyfile").read_text(encoding="utf-8")
    assert "reverse_proxy n8n:5678" in caddy and "admin off" in caddy
    assert "{$N8N_HOST}" in caddy and "Strict-Transport-Security" in caddy
    docs = (ASSETS / "README.md").read_text(encoding="utf-8")
    for requirement in (
        "Always Free-eligible",
        "Out of host capacity",
        "ONLY ONE scheduler",
        "NO PAYG",
        "reclamation",
        "linux/arm64",
        "NOT YET PROVISIONED",
    ):
        assert requirement in docs
    return pins


def docker_smoke(pins):
    """CI synthetic state only. No listener, published port, real key or credentials."""
    with tempfile.TemporaryDirectory(prefix="n8n-oci-ci-") as folder:
        tmp = Path(folder)
        data = tmp / "data"
        data.mkdir()
        os.chmod(tmp, 0o755)
        os.chmod(data, 0o777)  # Isolated nonsecret synthetic CI import, never production guidance.
        key = tmp / "key"
        key.write_text("synthetic-ci-only-encryption-key-0000000000", encoding="ascii")
        env = {
            **os.environ,
            "N8N_HOST": "n8n.example.org",
            "ACME_EMAIL": "operator@example.org",
            "N8N_DATA_DIR": str(data),
            "CADDY_DATA_DIR": str(tmp / "caddy-data"),
            "CADDY_CONFIG_DIR": str(tmp / "caddy-config"),
            "N8N_ENCRYPTION_KEY_FILE": str(key),
        }
        subprocess.run(
            ["docker", "compose", "-f", str(ASSETS / "compose.yaml"), "config", "--quiet"],
            check=True,
            env=env,
            timeout=30,
        )
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--platform",
                "linux/arm64",
                "-e",
                "N8N_HOST=n8n.example.org",
                "-e",
                "ACME_EMAIL=operator@example.org",
                "-v",
                f"{ASSETS / 'Caddyfile'}:/etc/caddy/Caddyfile:ro",
                pins[1],
                "caddy",
                "validate",
                "--config",
                "/etc/caddy/Caddyfile",
            ],
            check=True,
            timeout=180,
        )
        common = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--platform",
            "linux/arm64",
            "-e",
            "N8N_DIAGNOSTICS_ENABLED=false",
            "-e",
            "N8N_LOG_LEVEL=error",
            "-e",
            "N8N_ENCRYPTION_KEY_FILE=/run/secrets/n8n_encryption_key",
            "-v",
            f"{key}:/run/secrets/n8n_encryption_key:ro",
            "-v",
            f"{data}:/home/node/.n8n",
            "-v",
            f"{ROOT / 'ops/n8n/workflows'}:/workflows:ro",
            pins[0],
        ]
        subprocess.run([*common, "--version"], check=True, timeout=180)
        subprocess.run(
            [*common, "import:workflow", "--input=/workflows/rome_mobility_orchestration.json"],
            check=True,
            timeout=180,
        )
        subprocess.run([*common, "unpublish:workflow", "--all"], check=True, timeout=180)
        subprocess.run(
            [*common, "export:workflow", "--all", "--output=/home/node/.n8n/export.json"],
            check=True,
            timeout=180,
        )
        # Inspect private files as n8n's runtime UID, never relaxing their permissions.
        verification = (
            "const fs=require('fs');const assert=require('assert');"
            "const settings=JSON.parse(fs.readFileSync('/home/node/.n8n/config','utf8'));"
            "assert.strictEqual(settings.encryptionKey,"
            "fs.readFileSync('/run/secrets/n8n_encryption_key','utf8'));"
            "const workflows=JSON.parse(fs.readFileSync('/home/node/.n8n/export.json','utf8'));"
            "assert(workflows.length>0 && workflows.every(w=>w.active===false));"
            "assert(workflows.every(w=>w.nodes.every(n=>!('credentials' in n))));"
        )
        subprocess.run(
            [*common[:-1], "--entrypoint", "node", pins[0], "-e", verification],
            check=True,
            timeout=60,
        )
        # Delete private temporary state as its runtime UID; no backup/artifact upload.
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--platform",
                "linux/arm64",
                "-v",
                f"{data}:/home/node/.n8n",
                "--entrypoint",
                "node",
                pins[0],
                "-e",
                "require('fs').readdirSync('/home/node/.n8n').forEach(n=>require('fs').rmSync('/home/node/.n8n/'+n,{recursive:true,force:true}))",
            ],
            check=True,
            timeout=60,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    pins = validate()
    if args.docker:
        docker_smoke(pins)
    print("OCI n8n policy PASS; no infrastructure provisioned or schedule activated")


if __name__ == "__main__":
    main()
