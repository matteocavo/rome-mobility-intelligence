"""Deterministic synthetic data exclusively for tests and local fixture mode."""

import numpy as np
import pandas as pd

from app.contracts.operational_ml import CATEGORICAL, DELAY, LABEL, NUMERIC
from app.data.training_repository import TemporalPlan

FIXTURE_PLAN = TemporalPlan(100_000, 110_000, 120_000, 130_000, 132_000)


def synthetic_frame(rows=600, seed=42):
    if rows < 60:
        raise ValueError("Fixture requires >=60 rows")
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({name: rng.normal(size=rows) for name in NUMERIC})
    for name in CATEGORICAL:
        frame[name] = rng.choice(["a", "b", "c"], size=rows)
    frame["route_type"] = rng.choice([0, 1, 3], size=rows)
    frame["direction_id"] = rng.choice([0, 1], size=rows)
    frame["feed_timestamp"] = np.linspace(100_000, 129_900, rows).astype(int)
    frame["entity_id"] = [f"synthetic-{i}" for i in range(rows)]
    frame["trip_id"] = [f"fixture-trip-{i // 5}" for i in range(rows)]
    frame["stop_id"] = "fixture-stop"
    frame["stop_sequence"] = np.arange(rows) % 5
    frame["service_date"] = "SYNTHETIC"
    frame["label_horizon_seconds"] = 20
    frame["label_source_feed_timestamp"] = frame.feed_timestamp + 20
    frame[LABEL] = (frame.current_arrival_delay_seconds + rng.normal(0, 0.5, rows) > 0.4).astype(
        int
    )
    frame[DELAY] = np.where(frame[LABEL].eq(1), 400, 100)
    frame["sample_weight"] = 1.0
    frame.loc[frame.index[::13], "vehicle_speed"] = np.nan
    return frame
