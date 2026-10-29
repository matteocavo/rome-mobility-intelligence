"""Public browser boundary and actual repository SQL generation, without external services."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Select
from sqlalchemy.sql.elements import TextClause

from app.core.config import Settings
from app.main import create_app
from app.persistence.database import DatabaseTimeout, DatabaseUnavailable
from tests.conftest import SERVICE_KEY

PATHS = ["/public/predictions/current", "/public/predictions/history"]


class ReadDatabase:
    configured = True

    def __init__(self, *, empty=False):
        self.empty = empty
        self.statements = []
        self.now = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.epoch = int(self.now.timestamp())
        self.rows = [
            dict(
                route_id="route-demo",
                stop_id="stop-demo",
                stop_sequence=1,
                target_next_stop_id="next-demo",
                current_arrival_delay_seconds=120,
                major_delay_probability=0.8,
                predicted_major_delay=True,
                threshold=0.5,
                source_feed_timestamp=self.epoch,
                prediction_generated_at=self.now,
                model_version="PRIVATE-DIGEST",
                vehicle_id="vehicle-fixture",
                feature_contract_hash="PRIVATE-HASH",
                feed_hour="RAW-FEATURE",
            )
        ]

    @contextmanager
    def session(self):
        session = Mock()

        def execute(statement):
            self.statements.append(statement)
            result = Mock()
            if isinstance(statement, TextClause):
                return result
            assert isinstance(statement, Select), "Public path attempted a mutation"
            columns = set(statement.selected_columns.keys())
            if columns == {"source_feed_timestamp", "model_version"}:
                result.mappings.return_value.first.return_value = (
                    None
                    if self.empty
                    else {"source_feed_timestamp": self.epoch, "model_version": "PRIVATE-DIGEST"}
                )
            elif "threshold_min" in columns:
                result.mappings.return_value.one.return_value = dict(
                    count=len(self.rows),
                    major=len(self.rows),
                    mean_probability=0.8,
                    latest_prediction=self.now,
                    last_persisted=self.now,
                    threshold_min=0.5,
                    threshold_max=0.5,
                )
            else:
                limit = statement._limit_clause.value
                offset = statement._offset_clause.value
                result.mappings.return_value.all.return_value = (
                    [] if self.empty else self.rows[offset : offset + limit]
                )
            return result

        session.execute.side_effect = execute
        yield session


@pytest.fixture
def public_api():
    from app.contracts.public import page_response
    from app.persistence.public_repository import prediction
    from app.services.public_summary import NetworkSummary

    cfg = Settings(_env_file=None, environment="test", n8n_service_api_key=SERVICE_KEY)
    database = ReadDatabase()
    with TestClient(create_app(cfg)) as client:

        def page(query):
            now = datetime.now(timezone.utc)
            rows = [prediction(row) for row in database.rows]
            start = (query.page - 1) * query.page_size
            return page_response(
                query,
                total=len(rows),
                items=rows[start : start + query.page_size],
                coverage="current_scoring_population",
                watermark=database.now,
                now=now,
            )

        population = Mock()
        population.page.side_effect = page
        population.summary.return_value = NetworkSummary(
            query_generated_at=database.now,
            source_watermark=database.now,
            source_age_seconds=300,
            scored_count=25000,
            route_count=200,
            observed_delay_count=25000,
            median_observed_delay_seconds=100,
            p90_observed_delay_seconds=700,
            observed_delay_distribution=dict(early=0, minor=25000, moderate=0, major=0, critical=0),
            major_delay_count=5000,
            major_delay_rate=0.2,
            risk_status="complete_operational_model_population",
        )
        client.app.state.public_population = population
        client.app.state.public_history = Mock()
        client.app.state.public_history.page.side_effect = page
        yield client, database


PATHS = [
    "/public/status",
    "/public/summary",
    "/public/predictions/current",
    "/public/predictions/history",
]


@pytest.mark.parametrize("path", PATHS)
def test_anonymous_allowlist(public_api, path):
    client, _ = public_api
    response = client.get(path)
    assert response.status_code == 200
    for value in [
        "PRIVATE",
        "feature_contract_hash",
        "model_version",
        "entity_id",
        SERVICE_KEY,
    ]:
        assert value not in response.text


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD"])
def test_get_only(public_api, path, method):
    assert public_api[0].request(method, path).status_code == 405


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page_size=100",
        "sort=sql",
        "mode=rail",
        "page=1&page=2",
        "table=x",
        "query=x%00",
        "route=x%27%3BDROP",
    ],
)
def test_invalid_page_queries_rejected(public_api, query):
    client, _ = public_api
    assert client.get("/public/predictions/current?" + query).status_code == 422
    client.app.state.public_population.page.assert_not_called()


def test_pagination_metadata_is_not_summary_denominator(public_api):
    client, database = public_api
    database.rows *= 61
    first = client.get("/public/predictions/current?page=1&page_size=20").json()
    last = client.get("/public/predictions/current?page=4&page_size=20").json()
    assert first["total"] == 61 and len(first["items"]) == 20 and first["total_pages"] == 4
    assert len(last["items"]) == 1
    assert client.get("/public/summary").json()["scored_count"] == 25000


@pytest.mark.parametrize(
    "error,code", [(DatabaseTimeout("PRIVATE"), 504), (DatabaseUnavailable("SECRET"), 503)]
)
def test_page_errors_sanitized(public_api, error, code):
    client, _ = public_api
    client.app.state.public_history.page.side_effect = error
    response = client.get("/public/predictions/history")
    assert (
        response.status_code == code
        and "PRIVATE" not in response.text
        and "SECRET" not in response.text
    )


def test_rate_limit_and_default_cors(public_api):
    client, _ = public_api
    response = client.get("/public/status", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
    assert client.get("/model/info").status_code == 401


def test_exact_cors_and_no_service_key_preflight():
    cfg = Settings(
        _env_file=None, environment="test", cors_allowed_origins=["https://frontend.example.org"]
    )
    with TestClient(create_app(cfg)) as client:
        allowed = client.options(
            "/public/status",
            headers={
                "Origin": "https://frontend.example.org",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            allowed.status_code == 200
            and allowed.headers["access-control-allow-origin"] == "https://frontend.example.org"
        )
        rejected = client.options(
            "/public/status",
            headers={
                "Origin": "https://frontend.example.org",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-RMI-Service-Key",
            },
        )
        assert rejected.status_code == 400


def test_public_rate_bucket_is_global_and_separate(public_api):  # noqa: F811
    sample = public_api[0].app.state.public_population.summary.return_value
    cfg = Settings(
        _env_file=None, environment="test", rate_limit_public=1, n8n_service_api_key=SERVICE_KEY
    )
    with TestClient(create_app(cfg)) as client:
        client.app.state.public_population = Mock()
        client.app.state.public_population.summary.return_value = sample
        assert (
            client.get("/public/status", headers={"X-Forwarded-For": "192.0.2.1"}).status_code
            == 200
        )
        limited = client.get("/public/summary", headers={"X-Forwarded-For": "192.0.2.2"})
        assert limited.status_code == 429 and limited.headers["retry-after"]
        assert client.get("/health").status_code == 200
        assert client.get("/model/info").status_code == 401
