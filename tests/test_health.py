from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_and_skeleton_readiness():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["version"] == "0.1.0"
        assert client.get("/ready").json()["mode"] == "skeleton"
        assert client.get("/model/info").status_code == 503
        assert client.post("/predict").status_code == 404


def test_configured_missing_artifact_not_ready(tmp_path):
    with TestClient(
        create_app(Settings(_env_file=None, model_artifact_path=tmp_path / "missing"))
    ) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/ready").status_code == 503


def test_model_info_and_loaded_readiness(bundle):
    with TestClient(create_app(Settings(_env_file=None, model_artifact_path=bundle))) as client:
        assert client.get("/ready").json()["model_status"] == "loaded"
        data = client.get("/model/info").json()
        assert data["synthetic"] is True
        assert 0 < data["threshold"] < 1
        assert "validation_metrics" in data and "test_metrics" in data


def test_empty_artifact_environment_is_skeleton(monkeypatch):
    monkeypatch.setenv("MODEL_ARTIFACT_PATH", "")
    settings = Settings(_env_file=None)
    assert settings.model_artifact_path is None
    with TestClient(create_app(settings)) as client:
        assert client.get("/ready").json()["mode"] == "skeleton"
