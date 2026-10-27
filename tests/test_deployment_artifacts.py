import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def test_runtime_pins_match_reviewed_pins_without_ml_upgrades():
    def pins(name):
        result = {}
        for line in Path(name).read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                requirement = Requirement(line)
                result[canonicalize_name(requirement.name)] = str(requirement.specifier)
        return result

    runtime, dev = pins("requirements-runtime.txt"), pins("requirements-dev.txt")
    assert all(dev[name] == pin for name, pin in runtime.items())
    assert not {"pytest", "ruff", "httpx"} & set(runtime)
    assert {
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "psycopg",
        "databricks-sql-connector",
    } <= set(runtime)


def test_container_only_packages_code_with_immutable_nonroot_runtime():
    docker = Path("Dockerfile").read_text(encoding="utf-8")
    bases = [line for line in docker.splitlines() if line.startswith("FROM ")]
    assert len(bases) == 2
    assert all(
        re.match(r"FROM python:3\.12-slim-bookworm@sha256:[0-9a-f]{64}", line) for line in bases
    )
    assert "USER 10001:10001" in docker and "--only-binary=:all:" in docker
    assert '"scripts.serve"' in docker and '"scripts.healthcheck"' in docker
    assert "COPY . " not in docker and "COPY artifacts" not in docker and "COPY .env" not in docker
    assert "gcc" not in docker and "apt-get" not in docker
    ignore = Path(".dockerignore").read_text()
    assert "**" in ignore and "**/*.joblib" in ignore and "**/.env*" in ignore
    assert not Path("ops/n8n/compose.yml").exists()


def test_zero_cost_build_keeps_secrets_out_of_layers_and_model_private():
    docker = Path("Dockerfile.zero-cost").read_text(encoding="utf-8")
    assert "id=model-bootstrap_json,required=true" in docker
    assert "id=model-manifest_sha256,required=true" in docker
    assert "python -m scripts.bootstrap_model" in docker
    assert "COPY --from=builder /opt/rmi-model /opt/rmi-model" in docker
    assert "USER 10001:10001" in docker and "MODEL_BOOTSTRAP_ENABLED=false" in docker
    assert not any(line.startswith("ARG ") for line in docker.splitlines())
    assert "COPY /run/secrets" not in docker and "COPY artifacts" not in docker
    assert "ghcr.io" not in docker and "docker push" not in docker


def test_production_server_one_worker_no_forwarded_trust(monkeypatch):
    from scripts import serve

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr("sys.argv", ["serve"])
    run = Mock()
    monkeypatch.setattr(serve.uvicorn, "run", run)
    serve.main()
    options = run.call_args.kwargs
    assert options["workers"] == 1 and options["proxy_headers"] is False
    assert options["access_log"] is False and options["host"] == "127.0.0.1"
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(RuntimeError):
        serve.main()


def test_container_healthcheck_is_liveness_only(monkeypatch):
    from scripts import healthcheck

    monkeypatch.setenv("ALLOWED_HOSTS", json.dumps(["api.example.org"]))
    opener = MagicMock()
    response = opener.open.return_value.__enter__.return_value
    response.status = 200
    response.read.return_value = b'{"status":"ok"}'
    monkeypatch.setattr(healthcheck.urllib.request, "build_opener", lambda *args: opener)
    healthcheck.main()
    request = opener.open.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:8000/health"
    assert request.get_header("Host") == "api.example.org"
    assert opener.open.call_args.kwargs["timeout"] == 2


def test_invalid_production_startup_exits_without_traceback_or_private_settings():
    environment = {
        **os.environ,
        "ENVIRONMENT": "production",
        "ALLOWED_HOSTS": "[]",
        "N8N_SERVICE_API_KEY": "",
        "N8N_WEBHOOK_SECRET": "private-probe-value",
        "N8N_WEBHOOK_URL": "https://private-probe.app.n8n.cloud/webhook/probe",
    }
    result = subprocess.run(
        [sys.executable, "-m", "scripts.serve"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "server_start_failed" in output
    assert "private-probe" not in output and "Traceback" not in output
