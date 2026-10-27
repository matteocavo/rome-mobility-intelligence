from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pandas as pd
import pytest
from pydantic import SecretStr

from app.contracts.history import HistoryRecord
from app.data.databricks_client import DataAccessError, QueryTimeoutError
from app.persistence.database import DatabaseTimeout, DatabaseUnavailable
from app.persistence.history_repository import PredictionHistoryRepository
from tests.history_fakes import FakeDatabase
from tests.test_inference_api import api as api


@pytest.fixture
def history_api(api, frame):
    settings = api.app.state.settings
    settings.database_url = SecretStr("configured-placeholder")
    settings.enable_prediction_persistence = True
    database = FakeDatabase()
    api.app.state.history_repository = PredictionHistoryRepository(database, settings)
    source = frame.iloc[:2].copy()
    source["feed_timestamp"] = int(pd.Timestamp.now(tz="UTC").timestamp()) - 60
    api.app.state.current_repository = Mock()
    api.app.state.current_repository.latest.return_value = source
    yield api, database


def test_persistence_disabled_default_before_source_or_database(api):
    source = Mock()
    api.app.state.current_repository = source
    assert api.post("/predictions/current/persist").status_code == 503
    assert not api.app.state.settings.enable_prediction_persistence
    source.latest.assert_not_called()


def test_enabled_manual_batch_idempotent_second_call(history_api):
    api, database = history_api
    first = api.post("/predictions/current/persist?limit=2")
    second = api.post("/predictions/current/persist?limit=2")
    assert first.status_code == second.status_code == 200
    assert first.json()["rows_evaluated"] == first.json()["rows_inserted"] == 2
    assert second.json()["rows_inserted"] == 0 and second.json()["rows_existing"] == 2
    assert len(database.rows) == 2
    for row in database.rows.values():
        assert row["model_version"] == api.app.state.model.model_version
        assert row["threshold"] == api.app.state.model.threshold
        assert "feature_contract_hash" in row and "feed_hour" not in row


@pytest.mark.parametrize(
    "query",
    [
        "limit=101",
        "limit=0",
        "sql=SELECT+1",
        "table=other",
        "schema=other",
        "threshold=0.01",
        "model_path=private",
        "source_feed_timestamp=1",
        "filter=1=1",
        "limit=1&limit=2",
    ],
)
def test_persist_no_arbitrary_overrides(history_api, query):
    api, database = history_api
    assert api.post("/predictions/current/persist?" + query).status_code == 422
    assert database.rows == {}
    api.app.state.current_repository.latest.assert_not_called()


def test_persist_body_rejected(history_api):
    api, database = history_api
    assert api.post("/predictions/current/persist", json={"limit": 1}).status_code == 422
    assert database.rows == {}


@pytest.mark.parametrize(
    "error,status",
    [
        (DataAccessError("private"), 503),
        (QueryTimeoutError("private"), 504),
        (ValueError("private"), 422),
    ],
)
def test_current_source_failures_no_write(history_api, error, status):
    api, database = history_api
    api.app.state.current_repository.latest.side_effect = error
    response = api.post("/predictions/current/persist")
    assert response.status_code == status and "private" not in response.text
    assert database.rows == {}


@pytest.mark.parametrize(
    "error,status",
    [(DatabaseUnavailable("private DSN"), 503), (DatabaseTimeout("private host"), 504)],
)
def test_database_failures_no_false_success(history_api, error, status):
    api, _ = history_api
    repo = Mock()
    repo.insert_batch.side_effect = error
    repo.history.side_effect = error
    api.app.state.history_repository = repo
    for response in (api.post("/predictions/current/persist"), api.get("/predictions/history")):
        assert response.status_code == status and "private" not in response.text


def test_model_and_database_unconfigured_fail_closed(history_api):
    api, database = history_api
    api.app.state.model = None
    assert api.post("/predictions/current/persist").status_code == 503
    api.app.state.settings.database_url = SecretStr("")
    assert api.post("/predictions/current/persist").status_code == 503
    assert database.rows == {}


def test_history_typed_response_and_no_model_dependency(history_api):
    api, database = history_api
    assert api.post("/predictions/current/persist").status_code == 200
    api.app.state.model = None
    now = datetime.now(timezone.utc)
    records = [
        HistoryRecord(**row, id=i, created_at=now)
        for i, row in enumerate(database.rows.values(), 1)
    ]
    repo = Mock()
    repo.history.return_value = records
    api.app.state.history_repository = repo
    response = api.get("/predictions/history")
    assert response.status_code == 200
    data = response.json()
    assert data["rows"] == 2 and data["query_generated_at"].endswith("Z")
    assert "current_arrival_delay_seconds" in data["predictions"][0]
    assert "model_version" in data["predictions"][0]
    assert repo.history.call_args.args[0].limit == 50


def test_history_valid_filter_values_and_max_limit(history_api):
    api, _ = history_api
    repo = Mock()
    repo.history.return_value = []
    api.app.state.history_repository = repo
    now = datetime.now(timezone.utc)
    route = "'; DROP TABLE prediction_history; --"
    response = api.get(
        "/predictions/history",
        params={
            "route_id": route,
            "from": (now - timedelta(days=1)).isoformat(),
            "to": now.isoformat(),
            "limit": 200,
            "predicted_major_delay": "true",
        },
    )
    assert response.status_code == 200
    filters = repo.history.call_args.args[0]
    assert filters.route_id == route and filters.limit == 200
    assert filters.predicted_major_delay is True


@pytest.mark.parametrize(
    "params,status",
    [
        ({"from": "2026-10-27T00:00:00Z", "to": "2026-10-26T00:00:00Z"}, 400),
        ({"from": "2026-10-01T00:00:00Z", "to": "2026-10-27T00:00:00Z"}, 413),
        ({"from": "2026-10-27T00:00:00"}, 422),
        ({"limit": 201}, 422),
        ({"limit": 0}, 422),
        ({"sql": "SELECT 1"}, 422),
        ({"sort": "id"}, 422),
        ({"table": "other"}, 422),
        ({"model_path": "private"}, 422),
        ({"from_time": "2026-10-27T00:00:00Z"}, 422),
    ],
)
def test_history_invalid_filters_before_database(history_api, params, status):
    api, _ = history_api
    repo = Mock()
    api.app.state.history_repository = repo
    assert api.get("/predictions/history", params=params).status_code == status
    repo.history.assert_not_called()


def test_history_duplicate_keys_and_lower_limits(history_api):
    api, _ = history_api
    assert api.get("/predictions/history?limit=1&limit=2").status_code == 422
    api.app.state.settings.history_max_rows = 3
    repo = Mock()
    repo.history.return_value = []
    api.app.state.history_repository = repo
    assert api.get("/predictions/history").status_code == 200
    assert repo.history.call_args.args[0].limit == 3
    assert api.get("/predictions/history?limit=4").status_code == 422


def test_readiness_without_database_ping_and_openapi(history_api):
    api, _ = history_api
    assert api.get("/ready").json()["database_configured"] is True
    assert api.get("/ready").json()["prediction_persistence_enabled"] is True
    assert api.app.state.database._engine is None
    schema = api.get("/openapi.json").json()
    for path, method in [("/predictions/current/persist", "post"), ("/predictions/history", "get")]:
        assert {"200", "400", "413", "422", "503", "504"} <= set(
            schema["paths"][path][method]["responses"]
        )
    import json

    encoded = json.dumps(schema)
    assert "configured-placeholder" not in encoded and "DATABASE_URL" not in encoded
