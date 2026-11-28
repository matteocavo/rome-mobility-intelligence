"""Offline Gold contract/SQL/cache tests; every source and transport is synthetic."""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.contracts.analytics import AnalyticsQuery
from app.core.config import Settings
from app.data.databricks_client import DataAccessError, guard_select
from app.data.gold_repository import PREFIX, TABLES, GoldRepository
from app.main import create_app
from app.services.historical_analytics import HistoricalAnalytics

RELEASE = "12345678-1234-1234-1234-123456789abc"
EPOCH = 1795858177


def manifest():
    return dict(
        refresh_id=RELEASE,
        refresh_timestamp=datetime(2026, 11, 28, 10, tzinfo=timezone.utc),
        gold_versions_json=json.dumps({PREFIX + v: 10 + i for i, v in enumerate(TABLES.values())}),
        quality_status="PASSED",
        dashboard_ready="YES",
        ops_status="PINNED_INPUT_ALIGNED",
        ops_source_table="rome_transport.silver.realtime_enriched_observations",
        ops_source_version=263,
        ops_scoring_version=300,
        ops_latest_feed_timestamp=EPOCH,
        ops_observation_count=100,
    )


def row(**patch):
    return dict(
        key="network",
        total=100,
        known=90,
        missing=10,
        major=9,
        mean_seconds=15.0,
        median_seconds=10.0,
        p90_seconds=300.0,
        first_feed=EPOCH - 86400,
        last_feed=EPOCH,
        ops_release_id=RELEASE,
        ops_source_version=263,
        ops_metric_definition="reported_current_stop_arrival_delay_seconds",
        **patch,
    )


def service(rows=None):
    repository = Mock()
    repository.manifest.return_value = manifest()
    repository.read.return_value = pd.DataFrame([row()] if rows is None else rows)
    clock = Mock(return_value=0.0)
    return HistoricalAnalytics(repository, clock=clock), repository, clock


def test_manifest_versions_known_delay_denominator_and_cache():
    target, repo, clock = service()
    response = target.get(AnalyticsQuery())
    assert response.items[0].major_rate == 0.1  # 9/90, never 9/100
    assert response.source_version == 263 and response.scoring_version == 300
    assert response.gold_versions == {PREFIX + "executive_overview": 10}
    assert response.items[0].median_seconds == 10
    assert target.get(AnalyticsQuery()) is response
    assert repo.manifest.call_count == repo.read.call_count == 1
    assert repo.read.call_args.args[:4] == ("overview", 10, RELEASE, 263)
    clock.return_value = 601
    target.get(AnalyticsQuery())
    assert repo.manifest.call_count == repo.read.call_count == 2


@pytest.mark.parametrize(
    "patch",
    [
        {"known": 101},
        {"missing": 0},
        {"major": 91},
        {"total": 1.5},
        {"total": True},
        {"median_seconds": float("inf")},
        {"ops_release_id": "other"},
        {"ops_source_version": 262},
        {"ops_metric_definition": "future_target"},
    ],
)
def test_invalid_or_mixed_aggregates_fail_closed(patch):
    item = row()
    item.update(patch)
    target, repo, clock = service([item])
    with pytest.raises((ValueError, TypeError)):
        target.get(AnalyticsQuery())
    with pytest.raises(DataAccessError):
        target.get(AnalyticsQuery())
    assert repo.read.call_count == 1  # negative cache prevents repeated compute


def test_null_is_not_zero_and_zero_is_valid():
    missing = row()
    missing.update(
        known=0, missing=100, major=0, mean_seconds=None, median_seconds=None, p90_seconds=None
    )
    target, _, _ = service([missing])
    m = target.get(AnalyticsQuery()).items[0]
    assert m.major_rate is m.median_seconds is None
    zero = row()
    zero.update(major=0, mean_seconds=0.0, median_seconds=0.0, p90_seconds=0.0)
    target, _, _ = service([zero])
    m = target.get(AnalyticsQuery()).items[0]
    assert m.major_rate == m.median_seconds == 0


def test_temporal_counts_are_weighted_and_percentiles_are_not_averaged():
    first = row()
    first.update(key="2026-11-28", service_date=date(2026, 11, 28), weekday=6, hour=1)
    second = dict(first, total=10, known=10, missing=0, major=5, hour=2, median_seconds=999.0)
    target, repo, _ = service([first, second])
    result = target.get(
        AnalyticsQuery(view="temporal", **{"from": "2026-11-28", "to": "2026-11-28"})
    )
    assert result.daily[0].major_rate == 14 / 100
    assert result.daily[0].total == 110
    assert "median_seconds" not in result.daily[0].model_dump()
    # Temporal API exposes additive counts only, never recomposed percentiles.
    assert result.items == []
    assert result.heatmap[0].key == "6-01"


def test_default_period_is_28_service_dates_and_empty_ranking_is_empty():
    target, repo, _ = service([])
    result = target.get(AnalyticsQuery(view="temporal"))
    assert (result.period_to - result.period_from).days == 27
    assert result.items == result.daily == result.heatmap == []
    assert repo.read.call_args.args[-2:] == (result.period_from, result.period_to)


@pytest.mark.parametrize(
    "params",
    [
        {"view": "routes", "from": "2026-11-01", "to": "2026-11-02"},
        {"view": "temporal", "from": "2026-11-01"},
        {"view": "temporal", "from": "2026-11-02", "to": "2026-11-01"},
        {"view": "temporal", "from": "2026-10-01", "to": "2026-11-28"},
        {"view": "overview", "route": "64"},
    ],
)
def test_unsupported_filters_and_unbounded_periods_rejected(params):
    with pytest.raises(ValueError):
        AnalyticsQuery.model_validate(params)


def test_manifest_future_unvalidated_and_missing_version_rejected():
    for patch in [
        dict(quality_status="FAILED"),
        dict(ops_source_table="other"),
        dict(gold_versions_json="{}"),
        dict(refresh_id="not-a-uuid"),
        dict(refresh_timestamp=datetime.now(timezone.utc) + timedelta(days=1)),
    ]:
        target, repo, _ = service()
        repo.manifest.return_value.update(patch)
        with pytest.raises((ValueError, KeyError)):
            target.get(AnalyticsQuery())
        repo.read.assert_not_called()


def test_response_byte_budget_and_duplicate_grain(monkeypatch):
    target, _, _ = service([row(), row()])
    with pytest.raises(ValueError):
        target.get(AnalyticsQuery())
    target, _, _ = service()
    monkeypatch.setattr("app.services.historical_analytics.MAX_BYTES", 10)
    with pytest.raises(ValueError):
        target.get(AnalyticsQuery())


def test_sql_is_gold_only_version_pinned_and_parameterized():
    repo = GoldRepository(Settings(_env_file=None))
    repo.select = Mock(return_value=pd.DataFrame())
    for view in TABLES:
        repo.read(view, 12, RELEASE, 263, date(2026, 11, 1), date(2026, 11, 2))
        query = repo.select.call_args.args[0]
        guard_select(query)
        assert "VERSION AS OF 12" in query and "rome_transport.gold." in query
        assert "silver." not in query and "ops_release_id = :release" in query
        assert RELEASE not in query
        if view == "temporal":
            assert "service_date >= :start" in query
        if view in {"routes", "stops"}:
            assert "ops_ranking_eligible = true" in query
    assert repo.settings.databricks_warehouse_wake_enabled is False
    assert repo.settings.databricks_query_timeout_seconds == 8


@pytest.mark.parametrize("state", ["STOPPED", "STARTING", "UNKNOWN"])
def test_no_sql_when_warehouse_is_not_running(monkeypatch, state):
    settings = Settings(_env_file=None, databricks_http_path="/sql/1.0/warehouses/54e230332b887474")
    response = Mock()
    response.read.return_value = json.dumps({"state": state}).encode()
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=None)
    opener = Mock()
    opener.open.return_value = context
    monkeypatch.setattr(
        "app.data.gold_repository.urllib.request.build_opener", Mock(return_value=opener)
    )
    monkeypatch.setattr(
        "app.data.gold_repository.WorkloadCredentials", Mock(return_value=Mock(headers=lambda: {}))
    )
    repo = GoldRepository(settings)
    repo.client = Mock()
    with pytest.raises(DataAccessError):
        repo.manifest()
    repo.client.select.assert_not_called()
    assert opener.open.call_args.args[0].method == "GET"
    assert opener.open.call_args.kwargs["timeout"] == 5


def test_public_boundary_sanitized_errors_and_no_model_required(caplog):
    with TestClient(create_app(Settings(_env_file=None, environment="test"))) as client:
        target, repo, _ = service()
        client.app.state.historical_analytics = target
        result = client.get("/public/analytics/observed")
        assert result.status_code == 200
        assert result.json()["coverage"] == "gold_observed_history"
        assert len(result.content) < 256000
        assert client.get("/public/analytics/observed?route=64").status_code == 422
        assert client.get("/public/analytics/observed?view=routes&view=stops").status_code == 422
        broken = Mock()
        broken.get.side_effect = ValueError("Bearer private-token secret@example.com")
        client.app.state.historical_analytics = broken
        error = client.get("/public/analytics/observed")
        assert error.status_code == 503 and "private-token" not in error.text + caplog.text
        assert client.get("/health").status_code == 200


def test_service_day_can_cover_same_clock_hour_on_two_feed_weekdays():
    first = row()
    first.update(key="2026-11-27", service_date=date(2026, 11, 27), weekday=5, hour=1)
    second = dict(first, weekday=6)
    target, _, _ = service([first, second])
    result = target.get(
        AnalyticsQuery(view="temporal", **{"from": "2026-11-27", "to": "2026-11-27"})
    )
    assert result.daily[0].total == 200
    assert result.hourly[0].known == 180
    assert [v.key for v in result.heatmap] == ["5-01", "6-01"]
