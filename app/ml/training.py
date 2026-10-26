from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn

from app.contracts.operational_ml import CONTRACT, FEATURES, LABEL, NUMERIC, contract_digest
from app.contracts.schemas import ArtifactMetadata
from app.data.training_repository import TemporalPlan, validate_labeled
from app.ml.evaluation import evaluate
from app.ml.preprocessing import build_pipeline
from app.ml.threshold import select_threshold


def train(
    partitions: dict[str, pd.DataFrame],
    *,
    reference: dict,
    code_sha: str,
    synthetic: bool,
    seed: int = 42,
    freeze_callback=None,
):
    plan = TemporalPlan(**reference["temporal_plan"])
    if set(partitions) != {"train", "validation", "test"}:
        raise ValueError("Three frozen temporal partitions required")
    for name, start, end, cutoff in plan.partitions():
        frame = partitions[name]
        validate_labeled(frame)
        if not (
            frame.feed_timestamp.ge(start)
            & frame.feed_timestamp.lt(end)
            & frame.label_source_feed_timestamp.lt(cutoff)
        ).all():
            raise ValueError("Temporal leakage or immature labels")
        if set(frame[LABEL].unique()) != {0, 1}:
            raise ValueError("Both classes required")
    training, validation, test = [partitions[k] for k in ("train", "validation", "test")]
    if training[list(NUMERIC)].isna().all().any():
        raise ValueError("Entirely missing numeric training feature")
    # Dense HGB encoder has <=42+5*32 columns. Bound materialization before fitting.
    max_rows = max(len(f) for f in partitions.values())
    if max_rows * (42 + 5 * 32) * 8 > 256_000_000:
        raise ValueError("Dense preprocessing exceeds 256 MB matrix budget")
    candidates = {}
    fitted = {}
    weights = training.get("sample_weight", pd.Series(1.0, index=training.index)).to_numpy()
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Invalid inclusion weights")
    # Compare unweighted / inverse-inclusion weighted variants on natural validation.
    variants = [False, True] if not np.allclose(weights, 1) else [False]
    for kind in ("logistic_regression", "hist_gradient_boosting"):
        for weighted in variants:
            key = kind + ("_inclusion_weighted" if weighted else "_unweighted")
            pipeline = build_pipeline(kind, seed)
            pipeline.fit(
                training[list(FEATURES)],
                training[LABEL],
                classifier__sample_weight=weights if weighted else None,
            )
            p = pipeline.predict_proba(validation[list(FEATURES)])[:, 1]
            threshold, grid = select_threshold(validation[LABEL], p)
            metrics = evaluate(validation[LABEL], p, threshold)
            candidates[key] = {
                "model_type": kind,
                "weighted": weighted,
                "threshold": threshold,
                "metrics": metrics,
                "grid": grid,
            }
            fitted[key] = pipeline
    # No TEST access until model and threshold are frozen; no refit after selection.
    chosen = max(
        candidates,
        key=lambda k: (candidates[k]["metrics"]["f1"], candidates[k]["metrics"]["pr_auc"], k),
    )
    winner, pipeline = candidates[chosen], fitted[chosen]
    if freeze_callback is not None:
        freeze_callback(
            pipeline,
            {
                "selected_candidate": chosen,
                "threshold": winner["threshold"],
                "candidate_validation": candidates,
                "code_sha": code_sha,
                "training_data_reference": reference,
            },
        )
    test_probability = pipeline.predict_proba(test[list(FEATURES)])[:, 1]
    test_metrics = evaluate(test[LABEL], test_probability, winner["threshold"])
    metadata = ArtifactMetadata(
        model_type=winner["model_type"],
        trained_at=datetime.now(timezone.utc).isoformat(),
        contract_digest=contract_digest(),
        threshold=winner["threshold"],
        sklearn_version=sklearn.__version__,
        trained_code_sha=code_sha,
        training_data_reference={
            **reference,
            "selected_candidate": chosen,
            "input_contract": CONTRACT["event_id"],
        },
        validation_metrics=winner["metrics"],
        test_metrics=test_metrics,
        candidate_validation=candidates,
        threshold_grid=winner["grid"],
        synthetic=synthetic,
    )
    return pipeline, metadata
