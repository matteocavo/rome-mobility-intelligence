from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.contracts.operational_ml import CONTRACT, HASH
from app.core.config import Settings
from app.data.databricks_client import guard_select
from app.data.inference_repository import InferenceRepository
from app.data.training_repository import TrainingRepository, temporal_split
from app.ml.fixtures import FIXTURE_PLAN


def test_training_export_is_pinned_bounded_and_temporal(frame):
    splits = temporal_split(frame, FIXTURE_PLAN)
    client = MagicMock()
    replies = []
    for name, start, end, cutoff in FIXTURE_PLAN.partitions():
        population = frame[frame.feed_timestamp.ge(start) & frame.feed_timestamp.lt(end)]
        replies += [
            pd.DataFrame(
                [
                    {
                        "total": len(population),
                        "rejected": 0,
                        "purged": int(population.label_source_feed_timestamp.ge(cutoff).sum()),
                    }
                ]
            ),
            pd.DataFrame([{"duplicate_groups": 0}]),
            splits[name].copy(),
        ]
    client.select.side_effect = replies
    result, manifest = TrainingRepository(client, Settings(_env_file=None)).extract(
        FIXTURE_PLAN,
        version=12,
        train_budget=1000,
        evaluation_budget=1000,
        max_bytes=1_000_000,
        seed=42,
    )
    assert set(result) == {"train", "validation", "test"}
    assert manifest["version"] == 12
    for call in client.select.call_args_list:
        query, params = call.args
        guard_select(query)
        assert "VERSION AS OF 12" in query
        assert "SELECT *" not in query
        assert params["start"] < params["end"] <= params["cutoff"]
    assert manifest["partitions"]["test"]["unexpected_rejected_rows"] == 0


def test_training_export_blocks_unexpected_rejections():
    client = MagicMock()
    client.select.return_value = pd.DataFrame([{"total": 10, "rejected": 1, "purged": 0}])
    with pytest.raises(ValueError, match="excluded"):
        TrainingRepository(client, Settings(_env_file=None)).extract(
            FIXTURE_PLAN,
            version=12,
            train_budget=1000,
            evaluation_budget=1000,
            max_bytes=1_000_000,
            seed=42,
        )


def test_training_export_has_no_latest_version_fallback():
    client = MagicMock()
    with pytest.raises(ValueError, match="v12"):
        TrainingRepository(client, Settings(_env_file=None)).extract(
            FIXTURE_PLAN,
            version=8,
            train_budget=100,
            evaluation_budget=100,
            max_bytes=1_000_000,
            seed=42,
        )
    client.select.assert_not_called()


def test_stratified_training_preserves_strata_and_records_weights(frame):
    f = frame.copy()
    f["feed_hour"] = 10
    splits = temporal_split(f, FIXTURE_PLAN)
    training = splits["train"]
    names = ["service_date", "route_id", "feed_hour", CONTRACT["target"]["label_column"]]
    stats = training.groupby(names).size().reset_index(name="n")
    budget = 60
    stats["stratum_quota"] = (stats.n * (budget - len(stats)) // len(training) + 1).astype(int)
    sampled = training.merge(stats, on=names).rename(columns={"n": "stratum_n"})
    sampled = pd.concat(
        [group.iloc[: int(group.stratum_quota.iloc[0])] for _, group in sampled.groupby(names)],
        ignore_index=True,
    )
    replies = []
    for name, start, end, cutoff in FIXTURE_PLAN.partitions():
        population = f[f.feed_timestamp.ge(start) & f.feed_timestamp.lt(end)]
        replies += [
            pd.DataFrame(
                [
                    {
                        "total": len(population),
                        "rejected": 0,
                        "purged": int(population.label_source_feed_timestamp.ge(cutoff).sum()),
                    }
                ]
            ),
            pd.DataFrame([{"duplicate_groups": 0}]),
        ]
        if name == "train":
            replies += [stats[names + ["n"]], sampled]
        else:
            replies += [splits[name]]
    client = MagicMock()
    client.select.side_effect = replies
    result, manifest = TrainingRepository(client, Settings(_env_file=None)).extract(
        FIXTURE_PLAN,
        version=12,
        train_budget=budget,
        evaluation_budget=1000,
        max_bytes=1_000_000,
        seed=42,
    )
    assert len(result["train"]) <= budget
    assert result["train"].sample_weight.gt(1).all()
    allocation = manifest["partitions"]["train"]["strata_allocation"]
    assert len(allocation) == len(stats)
    assert all(0 < r["inclusion_probability"] <= 1 for r in allocation)
    query = manifest["partitions"]["train"]["query"]
    guard_select(query)
    assert "xxhash64" in query and "row_number()" in query


def scoring_frame(frame):
    sample = frame.iloc[:4].copy()
    feed = int(pd.Timestamp.now(tz="UTC").timestamp()) - 10
    sample["feed_timestamp"] = feed
    sample["target_next_stop_sequence"] = sample.stop_sequence + 1
    sample["feature_contract_hash"] = HASH
    sample["feature_prepared_at"] = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=2)
    sample["feature_preparation_batch_id"] = "fixture-batch"
    sample["source_silver_version"] = 12
    for name in CONTRACT["inference"]["columns"]:
        if name not in sample:
            sample[name] = None
    return sample[CONTRACT["inference"]["columns"]], feed


def test_inference_pinned_snapshot_and_hash(frame):
    sample, feed = scoring_frame(frame)
    client = MagicMock()
    client.select.return_value = sample
    result = InferenceRepository(client, Settings(_env_file=None)).snapshot(
        version=9,
        feed=feed,
        expected_rows=4,
        max_age_seconds=3600,
    )
    assert len(result) == 4
    query = client.select.call_args.args[0]
    guard_select(query)
    assert "VERSION AS OF 9" in query
    assert "target_realized" not in query


@pytest.mark.parametrize("bad", ["hash", "duplicate", "lineage", "future", "count", "stale"])
def test_inference_invalid_snapshot_rejected(frame, bad):
    sample, feed = scoring_frame(frame)
    if bad == "hash":
        sample.loc[0, "feature_contract_hash"] = "wrong"
    elif bad == "duplicate":
        sample.loc[1] = sample.loc[0]
    elif bad == "lineage":
        sample.loc[0, "feature_preparation_batch_id"] = "another"
    elif bad == "future":
        sample["feature_prepared_at"] = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
    elif bad == "stale":
        feed -= 7200
        sample["feed_timestamp"] = feed
    else:
        sample = sample.iloc[:2]
    client = MagicMock()
    client.select.return_value = sample
    with pytest.raises(ValueError):
        InferenceRepository(client, Settings(_env_file=None)).snapshot(
            version=9,
            feed=feed,
            expected_rows=4,
            max_age_seconds=3600,
        )
