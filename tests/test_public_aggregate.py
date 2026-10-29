"""Server-side aggregates are computed over the full filtered population, not a page."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Select
from sqlalchemy.dialects import postgresql

from app.contracts.public import AggregateQuery, PageQuery
from app.core.config import Settings
from app.main import create_app
from app.persistence.database import DatabaseUnavailable
from app.persistence.public_history import PublicHistory
from tests.test_public_pagination import population


def test_route_with_more_than_one_page_uses_full_route_population():
    service, _, _ = population(rows=101)
    result = service.aggregate(AggregateQuery(route="557"))
    assert result.total == 50 and result.total > 20
    assert sum(item.count for item in result.probability_bins) == 50
    assert result.observed_delay_count <= 50


def test_route_with_fewer_than_one_page():
    service, _, _ = population(rows=101)
    result = service.aggregate(AggregateQuery(route="85", query="real-fixture-vehicle-100"))
    assert result.total == 1 and sum(item.count for item in result.probability_bins) == 1


def test_route_without_observations_is_empty_not_zero_kpis():
    service, _, _ = population(rows=101)
    result = service.aggregate(AggregateQuery(route="missing"))
    assert result.total == 0 and result.average_probability is None
    assert result.max_observed_delay_seconds is None
    assert all(item.count == 0 and item.percentage == 0 for item in result.probability_bins)


def test_bins_cover_whole_population_and_boundaries():
    service, _, _ = population(rows=101)
    result = service.aggregate(AggregateQuery())
    assert result.total == 101 and len(result.probability_bins) == 10
    assert sum(item.count for item in result.probability_bins) == 101
    assert result.probability_bins[0].count > 0 and result.probability_bins[-1].count > 0
    assert abs(sum(item.percentage for item in result.probability_bins) - 100) < 0.1
    assert result.major_count == 65
    page = service.page(PageQuery())
    assert sum(item.count for item in result.probability_bins) != len(page.items)


def test_boundary_probability_goes_to_upper_bin():
    import numpy as np

    service, model, _ = population(rows=60)
    values = np.full(60, 0.55)
    values[:3] = [0.1, 0.0, 1.0]
    model.predict_proba.return_value = values
    counts = [item.count for item in service.aggregate(AggregateQuery()).probability_bins]
    assert counts[0] == 1 and counts[1] == 1 and counts[5] == 57 and counts[9] == 1


def test_aggregate_endpoint_validation_and_cold_start_errors():
    with TestClient(create_app(Settings(_env_file=None, environment="test"))) as client:
        for path in ("current", "history"):
            base = f"/public/predictions/{path}/aggregate"
            assert client.get(base + "?page=1").status_code == 422
            assert client.get(base + "?sort=risk_desc").status_code == 422
            assert client.get(base + "?route=a&route=b").status_code == 422
            assert client.get(base + "?route=x%27%3BDROP").status_code == 422
        client.app.state.public_population = Mock()
        client.app.state.public_population.aggregate.side_effect = Exception("PRIVATE")
        response = client.get("/public/predictions/current/aggregate")
        assert response.status_code == 503 and "PRIVATE" not in response.text


class AggregateDatabase:
    configured = True

    def __init__(self):
        self.statements = []
        hour = datetime(2026, 10, 29, 10)
        self.buckets = [
            dict(hour=datetime(2026, 10, 29, 11), count=70, major_count=7),
            dict(hour=hour, count=50, major_count=5),
        ]

    @contextmanager
    def session(self):
        session = Mock()

        def execute(statement):
            self.statements.append(statement)
            result = Mock()
            if isinstance(statement, Select):
                if statement._limit_clause is not None:
                    result.mappings.return_value.all.return_value = self.buckets
                else:
                    result.mappings.return_value.one.return_value = dict(
                        total=120, major_count=12, watermark=1_700_000_000
                    )
            return result

        session.execute.side_effect = execute
        yield session


def test_history_hourly_buckets_cover_filtered_total_not_page():
    database = AggregateDatabase()
    geography = Mock(stops={})
    result = PublicHistory(database, geography).aggregate(
        AggregateQuery(route="907", **{"from": "2026-10-29T00:00:00+00:00"})
    )
    assert result.total == 120 and result.total != 20
    assert [bucket.count for bucket in result.hourly] == [50, 70]
    assert result.hourly[0].hour.tzinfo == timezone.utc
    sql = " ".join(str(s.compile(dialect=postgresql.dialect())) for s in database.statements)
    assert "date_trunc" in sql and "route_id" in sql and "prediction_generated_at >=" in sql
    assert "LIMIT" in sql and "GROUP BY" in sql


def test_history_mode_filter_unavailable():
    with pytest.raises(DatabaseUnavailable):
        PublicHistory(AggregateDatabase(), Mock(stops={})).aggregate(AggregateQuery(mode="bus"))
