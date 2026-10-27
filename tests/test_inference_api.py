from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.contracts.inference import PredictRequest
from app.contracts.operational_ml import FEATURES, HASH
from app.core.config import Settings
from app.data.databricks_client import DataAccessError, QueryTimeoutError
from app.main import create_app


@pytest.fixture
def row(frame):
    return PredictRequest.model_validate(
        {k: None if pd.isna(v) else v for k, v in frame[list(FEATURES)].iloc[0].items()}
    ).model_dump()


@pytest.fixture
def api(bundle, bundle_trust):
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            model_artifact_path=bundle,
            model_artifact_root=bundle_trust["trusted_root"],
            model_artifact_manifest_sha256=bundle_trust["expected_manifest_sha256"],
        )
    )
    with TestClient(app) as client:
        yield client


def test_single_unknown_category_probability_and_mapping(api, row):
    row["route_id"] = "synthetic-unseen-route"
    row["feed_hour"] = "12"
    response = api.post("/predict", json=row)
    assert response.status_code == 200
    data = response.json()
    assert data["feature_contract_hash"] == HASH
    assert 0 <= data["major_delay_probability"] <= 1
    assert data["predicted_major_delay"] == (data["major_delay_probability"] >= data["threshold"])
    assert data["threshold"] == api.app.state.model.threshold


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "numeric",
        "fractional_category",
        "threshold",
        "model_path",
        "sql",
        "target",
    ],
)
def test_single_rejects_invalid_schema_and_overrides(api, row, change):
    if change == "missing":
        row.pop("feed_hour")
    elif change == "numeric":
        row["feed_hour"] = "invalid-private-value"
    elif change == "fractional_category":
        row["direction_id"] = 1.2
    else:
        row[change] = "private-override"
    response = api.post("/predict", json=row)
    assert response.status_code == 422
    assert "private" not in response.text


def test_batch_limits_empty_invalid_and_order(api, row):
    other = {**row, "feed_hour": 22, "current_arrival_delay_seconds": 700}
    rows = [row, other]
    data = api.post("/predict/batch", json=rows).json()
    assert data["rows"] == 2
    singles = [api.post("/predict", json=r).json()["major_delay_probability"] for r in rows]
    assert [p["major_delay_probability"] for p in data["predictions"]] == singles
    assert api.post("/predict/batch", json=[row] * 100).status_code == 200
    assert api.post("/predict/batch", json=[row] * 101).status_code == 413
    assert api.post("/predict/batch", json=[]).status_code == 400
    assert api.post("/predict/batch", json=[{**row, "extra": 1}]).status_code == 422


def test_current_shape_freshness_and_semantics(api, row):
    source = pd.DataFrame(
        [
            {
                **row,
                "feed_timestamp": int(pd.Timestamp.now(tz="UTC").timestamp()) - 60,
                "trip_id": "synthetic-trip",
                "vehicle_id": "synthetic-vehicle",
                "stop_id": "synthetic-stop",
            }
        ]
    )
    repo = Mock()
    repo.latest.return_value = source
    api.app.state.current_repository = repo
    response = api.get("/predictions/current?limit=1")
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == 1 and data["source_watermark"].endswith("Z")
    assert 59 <= data["source_age_seconds"] < 120
    prediction = data["predictions"][0]
    assert prediction["current_arrival_delay_seconds"] == row["current_arrival_delay_seconds"]
    assert prediction["trip_id"] == "synthetic-trip"
    assert prediction["predicted_major_delay"] == (
        prediction["major_delay_probability"] >= data["threshold"]
    )
    repo.latest.assert_called_once_with(1)


@pytest.mark.parametrize(
    "query",
    [
        "limit=101",
        "limit=0",
        "limit=-1",
        "limit=1&limit=2",
        "table=other",
        "schema=other",
        "catalog=other",
        "sql=SELECT+1",
        "filter=1=1",
        "artifact_path=private",
        "threshold=0.1",
        "limit=1%3BDROP+TABLE+x",
    ],
)
def test_current_no_query_injection_surface(api, query):
    repo = Mock()
    api.app.state.current_repository = repo
    assert api.get("/predictions/current?" + query).status_code == 422
    repo.latest.assert_not_called()


def test_query_failures_are_sanitized_and_deadline_is_504(api):
    repo = Mock()
    api.app.state.current_repository = repo
    repo.latest.side_effect = DataAccessError("private-host-or-secret")
    response = api.get("/predictions/current")
    assert response.status_code == 503 and "private" not in response.text

    repo.latest.side_effect = QueryTimeoutError("private-details")
    assert api.get("/predictions/current").status_code == 504
    repo.latest.side_effect = ValueError("private-source")
    assert api.get("/predictions/current").status_code == 422


def test_model_not_ready_and_synthetic_not_operational(row, bundle, bundle_trust):
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.post("/predict", json=row).status_code == 503
    settings = Settings(
        _env_file=None,
        model_artifact_path=bundle,
        model_artifact_root=bundle_trust["trusted_root"],
        model_artifact_manifest_sha256=bundle_trust["expected_manifest_sha256"],
    )
    with TestClient(create_app(settings)) as client:
        assert client.post("/predict", json=row).status_code == 503


def test_openapi_and_readiness_no_sql(api):
    repo = Mock()
    api.app.state.current_repository = repo
    schema = api.get("/openapi.json").json()
    fields = schema["components"]["schemas"]["PredictRequest"]["properties"]
    assert tuple(fields) == FEATURES
    assert schema["components"]["schemas"]["PredictRequest"]["additionalProperties"] is False
    assert len(schema["components"]["schemas"]["PredictRequest"]["required"]) == 47
    for route, method in [
        ("/predict", "post"),
        ("/predict/batch", "post"),
        ("/predictions/current", "get"),
    ]:
        assert {"200", "400", "413", "422", "503", "504"} <= set(
            schema["paths"][route][method]["responses"]
        )
    assert api.get("/ready").json()["artifact_integrity"] == "verified"
    assert api.get("/ready").json()["databricks_readiness"] == "not_checked"
    repo.latest.assert_not_called()
    info = api.get("/model/info").json()
    assert info["artifact_integrity_verified"] and info["serving_status"] == "ready"


def test_post_query_overrides_rejected(api, row):
    assert api.post("/predict?threshold=0.1", json=row).status_code == 422
    assert api.post("/predict?model_path=private", json=row).status_code == 422
    assert api.post("/predict/batch?artifact_path=private", json=[row]).status_code == 422


def test_current_default_no_staleness_claim(api, row):
    source = pd.DataFrame([{**row, "feed_timestamp": 1700000000}])
    repo = Mock()
    repo.latest.return_value = source
    api.app.state.current_repository = repo
    response = api.get("/predictions/current")
    assert response.status_code == 200
    assert response.json()["source_age_seconds"] > 3600
    assert response.json()["predictions"][0]["trip_id"] is None
    repo.latest.assert_called_once_with(50)


def test_current_invalid_feature_projection_fails_closed(api, row):
    repo = Mock()
    repo.latest.return_value = pd.DataFrame([{**row, "feed_timestamp": 1700000000}]).drop(
        columns="feed_hour"
    )
    api.app.state.current_repository = repo
    assert api.get("/predictions/current").status_code == 422


def test_model_is_loaded_once_not_per_request(api, row, monkeypatch):
    def forbidden_reload(*args, **kwargs):
        raise AssertionError("Model reload is forbidden during inference")

    monkeypatch.setattr("app.services.model_service.load", forbidden_reload)
    assert api.post("/predict", json=row).status_code == 200
    assert api.post("/predict/batch", json=[row]).status_code == 200


def test_workload_pat_rejected_at_current_boundary(api):
    from app.core.workload_auth import WorkloadAuthenticationError, WorkloadCredentials
    from app.data.databricks_client import DatabricksClient

    settings = Settings(
        _env_file=None,
        databricks_server_hostname="test.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/test",
        databricks_token="private-pat",
        databricks_client_id="8827c903-11f1-441b-a455-064d0b25dd84",
    )
    with pytest.raises(WorkloadAuthenticationError):
        WorkloadCredentials(settings)
    connector = Mock()
    with pytest.raises(DataAccessError):
        DatabricksClient(settings, connect=connector).select("SELECT 1", max_rows=1)
    connector.assert_not_called()


def test_model_predict_proba_is_serialized(api, row, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    lock = threading.Lock()
    active = peak = 0

    def probability(frame):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.01)
        with lock:
            active -= 1
        return np.tile([0.8, 0.2], (len(frame), 1))

    model = api.app.state.model
    monkeypatch.setattr(model.pipeline, "predict_proba", probability)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: model.predict_one(row), range(8)))
    assert peak == 1 and len(results) == 8


def test_model_inference_rejects_invalid_probabilities(api, row, monkeypatch):
    monkeypatch.setattr(
        api.app.state.model.pipeline, "predict_proba", lambda frame: np.array([[np.nan, np.inf]])
    )
    assert api.post("/predict", json=row).status_code == 422


def test_configured_lower_batch_limit(api, row):
    api.app.state.settings.inference_max_batch_rows = 2
    assert api.post("/predict/batch", json=[row] * 3).status_code == 413
    repo = Mock()
    repo.latest.side_effect = DataAccessError("unavailable")
    api.app.state.current_repository = repo
    assert api.get("/predictions/current").status_code == 503
    repo.latest.assert_called_once_with(2)
