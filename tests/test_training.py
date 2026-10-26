from dataclasses import asdict

import pytest

from app.contracts.operational_ml import DELAY, LABEL
from app.data.training_repository import TemporalPlan, temporal_split, validate_labeled
from app.ml.fixtures import FIXTURE_PLAN
from app.ml.threshold import select_threshold
from app.ml.training import train


def test_temporal_split_and_maturing_labels(frame):
    f = frame.copy()
    f.loc[0, "feed_timestamp"] = FIXTURE_PLAN.validation_start - 10
    f.loc[0, "label_source_feed_timestamp"] = FIXTURE_PLAN.validation_start + 10
    splits = temporal_split(f, FIXTURE_PLAN)
    assert 0 not in splits["train"].index
    assert splits["train"].feed_timestamp.max() < splits["validation"].feed_timestamp.min()
    assert splits["validation"].feed_timestamp.max() < splits["test"].feed_timestamp.min()
    assert set(splits["train"].feed_timestamp).isdisjoint(splits["validation"].feed_timestamp)


@pytest.mark.parametrize("bad", ["label", "horizon", "duplicate", "null_key", "delay"])
def test_label_population_fail_fast(frame, bad):
    f = frame.copy()
    if bad == "label":
        f.loc[0, LABEL] = 1 - f.loc[0, LABEL]
    elif bad == "horizon":
        f.loc[0, "label_horizon_seconds"] = 1900
    elif bad == "duplicate":
        f.loc[1] = f.loc[0]
    elif bad == "null_key":
        f.loc[0, "entity_id"] = None
    else:
        f.loc[0, DELAY] = 50000
    with pytest.raises(ValueError):
        validate_labeled(f)


def test_bad_temporal_plan():
    with pytest.raises(ValueError):
        TemporalPlan(10, 30, 20, 40, 50)


def test_threshold_is_selected_on_validation():
    threshold, grid = select_threshold([0, 0, 1, 1], [0.1, 0.2, 0.7, 0.8], [0.15, 0.5, 0.75])
    assert threshold == 0.5
    assert len(grid) == 3
    assert set(grid[0]) == {"threshold", "precision", "recall", "f1"}


def test_training_candidates_and_test_isolation(frame, trained):
    _, metadata = trained
    assert metadata.synthetic
    assert set(metadata.candidate_validation) == {
        "logistic_regression_unweighted",
        "hist_gradient_boosting_unweighted",
    }
    partitions = temporal_split(frame, FIXTURE_PLAN)
    partitions["test"] = partitions["test"].copy()
    partitions["test"][LABEL] = 1 - partitions["test"][LABEL]
    partitions["test"][DELAY] = partitions["test"][LABEL].map({0: 100, 1: 400})
    _, flipped = train(
        partitions,
        reference={"temporal_plan": asdict(FIXTURE_PLAN)},
        code_sha="fixture-test",
        synthetic=True,
    )
    assert flipped.threshold == metadata.threshold
    assert flipped.model_type == metadata.model_type
    assert flipped.candidate_validation == metadata.candidate_validation
    assert flipped.test_metrics != metadata.test_metrics


def test_training_rejects_leakage(frame):
    partitions = temporal_split(frame, FIXTURE_PLAN)
    partitions["train"].loc[0, "label_source_feed_timestamp"] = FIXTURE_PLAN.test_start
    with pytest.raises(ValueError):
        train(
            partitions,
            reference={"temporal_plan": asdict(FIXTURE_PLAN)},
            code_sha="fixture",
            synthetic=True,
        )
