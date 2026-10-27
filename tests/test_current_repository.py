from unittest.mock import Mock

import pandas as pd
import pytest

from app.contracts.operational_ml import HASH
from app.core.config import Settings
from app.data.current_repository import CurrentScoringRepository
from app.data.databricks_client import guard_select


@pytest.fixture
def scoring_frame(frame):
    result = frame.iloc[:2].copy()
    result["feed_timestamp"] = int(pd.Timestamp.now(tz="UTC").timestamp()) - 60
    result["feature_prepared_at"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=30)
    result["source_silver_version"] = 1
    result["feature_preparation_batch_id"] = "synthetic-batch"
    result["stop_sequence"] = 1
    result["target_next_stop_sequence"] = 2
    result["snapshot_rows"] = 2
    result["grain_rows"] = 1
    result["feature_contract_hash"] = HASH
    for name in (
        "feature_contract_hash",
        "source_silver_version",
        "feature_preparation_batch_id",
        "feature_prepared_at",
    ):
        result[name + "_min"] = result[name].iloc[0]
        result[name + "_max"] = result[name].iloc[0]
        result[name + "_count"] = 2
    return result


def test_current_fixed_query_budgets_and_contract(scoring_frame):
    client = Mock()
    client.select.return_value = scoring_frame
    repo = CurrentScoringRepository(client, Settings(_env_file=None))
    assert len(repo.latest(2)) == 2
    args, kwargs = client.select.call_args
    guard_select(args[0])
    assert "MAX(feed_timestamp)" in args[0]
    assert "ORDER BY" in args[0] and "LIMIT :requested_limit" in args[0]
    assert "`rome_transport`.`features`.`next_stop_delay_scoring`" in args[0]
    assert args[1] == {"requested_limit": 2}
    assert kwargs == {"max_rows": 2, "max_bytes": 8_000_000}


@pytest.mark.parametrize(
    "problem",
    ["empty", "hash", "grain", "lineage", "missing_lineage", "future", "feature", "next_stop"],
)
def test_current_invalid_snapshot_fails_closed(scoring_frame, problem):
    frame = scoring_frame.copy()
    if problem == "empty":
        frame = frame.iloc[:0]
    elif problem == "hash":
        frame["feature_contract_hash"] = "wrong"
    elif problem == "grain":
        frame["grain_rows"] = 2
    elif problem == "lineage":
        frame["source_silver_version_max"] = 2
    elif problem == "missing_lineage":
        frame["feature_prepared_at_count"] = 1
    elif problem == "future":
        frame["feed_timestamp"] = int(pd.Timestamp.now(tz="UTC").timestamp()) + 10000
    elif problem == "feature":
        frame["feed_hour"] = "not-numeric"
    else:
        frame["target_next_stop_sequence"] = 0
    client = Mock()
    client.select.return_value = frame
    with pytest.raises((ValueError, TypeError)):
        CurrentScoringRepository(client, Settings(_env_file=None)).latest(2)


@pytest.mark.parametrize("limit", [0, 101, True, "1; SELECT 1"])
def test_invalid_limit_no_connection(limit):
    client = Mock()
    with pytest.raises(ValueError):
        CurrentScoringRepository(client, Settings(_env_file=None)).latest(limit)
    client.select.assert_not_called()
