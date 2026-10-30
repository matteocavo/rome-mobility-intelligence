from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import SERVICE_KEY


def security_settings(**kwargs):
    return Settings(n8n_service_api_key=SERVICE_KEY, **kwargs)


def service_client(app):
    return TestClient(app, headers={"X-RMI-Service-Key": SERVICE_KEY})


def test_health_and_skeleton_readiness():
    with service_client(create_app(security_settings(_env_file=None))) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["version"] == "1.0.1"
        assert client.get("/ready").json()["mode"] == "skeleton"
        assert client.get("/model/info").status_code == 503
        assert client.post("/predict").status_code == 503
        assert client.get("/ready").status_code == 503


def test_configured_missing_artifact_not_ready(tmp_path):
    with service_client(
        create_app(security_settings(_env_file=None, model_artifact_path=tmp_path / "missing"))
    ) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/ready").status_code == 503


def test_existing_model_without_external_trust_is_not_ready(bundle):
    with service_client(
        create_app(security_settings(_env_file=None, model_artifact_path=bundle))
    ) as client:
        assert client.get("/ready").status_code == 503
        assert client.get("/model/info").status_code == 503


def test_model_info_and_loaded_readiness(bundle, bundle_trust):
    with service_client(
        create_app(
            security_settings(
                _env_file=None,
                environment="test",
                model_artifact_path=bundle,
                model_artifact_root=bundle_trust["trusted_root"],
                model_artifact_manifest_sha256=bundle_trust["expected_manifest_sha256"],
            )
        )
    ) as client:
        assert client.get("/ready").json()["model_status"] == "loaded"
        data = client.get("/model/info").json()
        assert data["synthetic"] is True
        assert 0 < data["threshold"] < 1
        assert "validation_metrics" in data and "test_metrics" in data
        assert "training_data_reference" in data


def test_empty_artifact_environment_is_skeleton(monkeypatch):
    monkeypatch.setenv("MODEL_ARTIFACT_PATH", "")
    settings = security_settings(_env_file=None)
    assert settings.model_artifact_path is None
    with service_client(create_app(settings)) as client:
        assert client.get("/ready").json()["mode"] == "skeleton"


def test_model_info_reference_excludes_private_queries(bundle, bundle_trust):
    from app.services.model_service import ModelService

    service = ModelService(bundle, **bundle_trust)
    service.metadata.training_data_reference["partitions"] = {
        "train": {
            "exported_rows": 200,
            "query": "private-sql",
            "parameters": {"start": 1},
            "strata_allocation": [{"n": 10}],
            "artifact_path": "private-local-path",
            "secret_reference": "private-credential-store",
        }
    }
    reference = service.info()["training_data_reference"]
    assert reference["partitions"]["train"] == {"exported_rows": 200}
