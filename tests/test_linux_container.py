"""Opt-in CI image build + offline synthetic serving under the actual RAM cap."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.environ.get("RMI_CONTAINER_SMOKE") != "1", reason="Explicit Linux Docker CI smoke only"
)
def test_linux_docker_build_and_synthetic_memory(bundle):
    assert os.name == "posix" and shutil.which("docker")
    subprocess.run(["docker", "build", "--tag", "rmi-offline-smoke", "."], check=True, timeout=900)
    pin = hashlib.sha256((bundle / "checksums.json").read_bytes()).hexdigest()
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "0.1",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=32m",
            "--mount",
            f"type=bind,src={bundle},dst=/opt/models/bundle,readonly",
            "--mount",
            f"type=bind,src={Path('scripts/container_probe.py').resolve()},dst=/srv/app/probe.py,readonly",
            "--env",
            "PYTHONPATH=/srv/app",
            "--env",
            "ENVIRONMENT=test",
            "--env",
            "MODEL_ARTIFACT_ROOT=/opt/models",
            "--env",
            "MODEL_ARTIFACT_PATH=/opt/models/bundle",
            "--env",
            f"MODEL_ARTIFACT_MANIFEST_SHA256={pin}",
            "--env",
            'ALLOWED_HOSTS=["api.example.org"]',
            "--env",
            "N8N_SERVICE_API_KEY=synthetic-container-probe-key-00000000000",
            "--env",
            "OMP_NUM_THREADS=1",
            "--env",
            "OPENBLAS_NUM_THREADS=1",
            "rmi-offline-smoke",
            "python",
            "probe.py",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert '"probe": "PASS"' in result.stdout
    assert '"synthetic": true' in result.stdout
    # Only allowlisted memory/probe fields, never payload or executable bundle output.
    print(result.stdout)
