from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from app.contracts.operational_ml import CONTRACT, DELAY, FEATURES, HASH, KEY, LABEL
from app.core.config import Settings
from app.data.databricks_client import DatabricksClient, identifier, table_name
from app.ml.preprocessing import FeatureValidator


@dataclass(frozen=True)
class TemporalPlan:
    start: int
    validation_start: int
    test_start: int
    end: int
    evaluation_cutoff: int

    def __post_init__(self):
        values = tuple(asdict(self).values())
        if any(type(x) is not int or x < 0 for x in values):
            raise ValueError("Explicit nonnegative UTC epochs required")
        if not self.start < self.validation_start < self.test_start < self.end:
            raise ValueError("Non-overlapping chronological partitions required")
        if self.evaluation_cutoff < self.end:
            raise ValueError("Evaluation labels must mature after test window")

    def partitions(self):
        return [
            ("train", self.start, self.validation_start, self.validation_start),
            ("validation", self.validation_start, self.test_start, self.test_start),
            ("test", self.test_start, self.end, self.evaluation_cutoff),
        ]


def validate_labeled(frame: pd.DataFrame) -> None:
    required = (
        set(FEATURES)
        | set(KEY)
        | {LABEL, DELAY, "label_source_feed_timestamp", "label_horizon_seconds"}
    )
    if not required.issubset(frame) or frame.empty or frame.columns.duplicated().any():
        raise ValueError("Incomplete training data")
    if frame[list(KEY)].isna().any().any() or frame.duplicated(list(KEY)).any():
        raise ValueError("Null or duplicate observation key")
    FeatureValidator().transform(frame[list(FEATURES)])
    delay = pd.to_numeric(frame[DELAY], errors="raise")
    horizon = frame.label_source_feed_timestamp - frame.feed_timestamp
    valid = (
        delay.notna()
        & (delay.abs() <= 43200)
        & frame[LABEL].isin([0, 1])
        & (frame[LABEL] == (delay >= 300).astype(int))
        & horizon.between(1, 1800)
        & (horizon == frame.label_horizon_seconds)
    )
    if not valid.all():
        raise ValueError("Invalid stored label, delay or label availability")


def temporal_split(frame: pd.DataFrame, plan: TemporalPlan) -> dict[str, pd.DataFrame]:
    validate_labeled(frame)
    result = {}
    for name, start, end, cutoff in plan.partitions():
        partition = frame[
            (frame.feed_timestamp >= start)
            & (frame.feed_timestamp < end)
            & (frame.label_source_feed_timestamp < cutoff)
        ].copy()
        if partition.empty or set(partition[LABEL].unique()) != {0, 1}:
            raise ValueError(f"Partition {name} requires both classes")
        result[name] = partition
    return result


class TrainingRepository:
    def __init__(self, client: DatabricksClient, settings: Settings):
        self.client, self.settings = client, settings

    def extract(
        self,
        plan: TemporalPlan,
        *,
        version: int,
        train_budget: int,
        evaluation_budget: int,
        max_bytes: int,
        seed: int,
        evaluation_sample: bool = False,
    ) -> tuple[dict[str, pd.DataFrame], dict]:
        if type(version) is not int or version != CONTRACT["training"]["validated_version"]:
            raise ValueError("Only explicitly validated labeled v12 supported; no fallback")
        if min(train_budget, evaluation_budget, max_bytes) < 1 or type(seed) is not int:
            raise ValueError("Explicit positive capacity and integer seed required")
        table = table_name(self.settings, self.settings.training_table)
        columns = list(
            dict.fromkeys(
                CONTRACT["training"]["metadata_columns"] + list(FEATURES) + [DELAY, LABEL]
            )
        )
        projection = ", ".join(identifier(c) for c in columns)
        keys = ", ".join(identifier(c) for c in KEY)
        strata = f"service_date, route_id, feed_hour, `{LABEL}`"
        datasets, manifest = (
            {},
            {
                "table": table,
                "version": version,
                "feature_contract_hash": HASH,
                "temporal_plan": asdict(plan),
                "seed": seed,
                "partitions": {},
                "sampling_algorithm": "floor(n*(budget-strata)/total)+1 per train stratum",
                "ordering": "xxhash64(full observation key, seed), full observation key",
            },
        )
        for name, start, end, cutoff in plan.partitions():
            params = {"start": start, "end": end, "cutoff": cutoff}
            base = (
                f"SELECT {projection} FROM {table} VERSION AS OF {version} "
                "WHERE feed_timestamp >= :start AND feed_timestamp < :end"
            )
            valid = (
                "label_source_feed_timestamp > feed_timestamp "
                "AND label_horizon_seconds BETWEEN 1 AND 1800 "
                "AND label_horizon_seconds = label_source_feed_timestamp-feed_timestamp "
                f"AND abs(`{DELAY}`) <= 43200 "
                f"AND `{LABEL}` = CAST(`{DELAY}` >= 300 AS INT) AND "
                + " AND ".join(f"{identifier(k)} IS NOT NULL" for k in KEY)
            )
            audit = self.client.select(
                f"SELECT count(*) AS total, "
                f"count_if(NOT coalesce(({valid}), false)) AS rejected, "
                "count_if(label_source_feed_timestamp >= :cutoff) AS purged "
                f", count_if(label_source_feed_timestamp < :cutoff AND `{LABEL}`=1) "
                "AS eligible_positives "
                f"FROM ({base}) AS population",
                params,
                max_rows=1,
            ).iloc[0]
            if int(audit.rejected) != 0:
                raise ValueError("Unexpected excluded rows; export blocked")
            eligible = base + " AND label_source_feed_timestamp < :cutoff"
            duplicate = self.client.select(
                f"SELECT count(*) AS duplicate_groups FROM (SELECT {keys} "
                f"FROM ({eligible}) AS eligible GROUP BY {keys} HAVING count(*)>1) AS d",
                params,
                max_rows=1,
            ).iloc[0]
            if int(duplicate.duplicate_groups):
                raise ValueError("Duplicate source grain; export blocked")
            count = int(audit.total) - int(audit.purged)
            sampled_evaluation = name != "train" and count > evaluation_budget
            if name != "train":
                if sampled_evaluation and not evaluation_sample:
                    raise ValueError("Full natural-prevalence evaluation exceeds measured budget")
                query = eligible
                if sampled_evaluation:
                    params.update(
                        evaluation_seed=seed + (1 if name == "validation" else 2),
                        evaluation_limit=evaluation_budget,
                    )
                    query += (
                        f" ORDER BY xxhash64({keys}, :evaluation_seed), {keys} "
                        "LIMIT :evaluation_limit"
                    )
                limit = evaluation_budget
            elif count <= train_budget:
                query, limit = eligible, train_budget
            else:
                stats = self.client.select(
                    f"SELECT {strata}, count(*) AS n FROM ({eligible}) AS eligible "
                    f"GROUP BY {strata}",
                    params,
                    max_rows=train_budget,
                )
                number = len(stats)
                if number >= train_budget:
                    raise ValueError("Budget cannot preserve every training stratum")
                params.update(seed=seed, remaining=train_budget - number, total=count)
                ranked = (
                    f"SELECT eligible.*, count(*) OVER (PARTITION BY {strata}) AS stratum_n, "
                    f"row_number() OVER (PARTITION BY {strata} ORDER BY "
                    f"xxhash64({keys}, :seed), {keys}) AS sample_rank "
                    f"FROM ({eligible}) AS eligible"
                )
                query = (
                    f"SELECT {projection}, stratum_n, "
                    "least(stratum_n, floor(stratum_n*:remaining/:total)+1) AS stratum_quota "
                    f"FROM ({ranked}) AS ranked WHERE sample_rank <= "
                    "least(stratum_n, floor(stratum_n*:remaining/:total)+1)"
                )
                limit = train_budget
            frame = self.client.select(query, params, max_rows=limit, max_bytes=max_bytes)
            validate_labeled(frame)
            if name != "train" or count <= train_budget:
                expected_count = min(count, evaluation_budget) if name != "train" else count
                if len(frame) != expected_count:
                    raise ValueError("Incomplete export")
                frame["sample_weight"] = 1.0
            else:
                frame["sample_weight"] = frame.stratum_n / frame.stratum_quota
                expected = np.minimum(
                    stats.n, np.floor(stats.n * (train_budget - len(stats)) / count) + 1
                ).sum()
                if len(frame) != int(expected):
                    raise ValueError("Sampling allocation mismatch")
            if set(frame[LABEL].unique()) != {0, 1}:
                raise ValueError("Both classes required in each partition")
            import hashlib

            checksum = hashlib.sha256(
                frame.sort_values(list(KEY))[list(KEY)].to_csv(index=False).encode()
            ).hexdigest()
            datasets[name] = frame
            manifest["partitions"][name] = {
                "source_rows": int(audit.total),
                "purged_rows": int(audit.purged),
                "unexpected_rejected_rows": 0,
                "eligible_rows": count,
                "eligible_positives": int(audit.eligible_positives)
                if "eligible_positives" in audit
                else None,
                "exported_rows": len(frame),
                "positive_rate": float(frame[LABEL].mean()),
                "snapshots": int(frame.feed_timestamp.nunique()),
                "min_feed": int(frame.feed_timestamp.min()),
                "max_feed": int(frame.feed_timestamp.max()),
                "selected_keys_sha256": checksum,
                "query": query,
                "parameters": params,
                "inclusion_weights": "stratum_n/stratum_quota" if "stratum_n" in frame else "1",
                "evaluation_sampling": (
                    "uniform full-grain hash rank, independent of label"
                    if sampled_evaluation
                    else "none"
                ),
                "evaluation_inclusion_probability": len(frame) / count if name != "train" else None,
            }
            if "stratum_n" in frame:
                allocation = stats.copy()
                allocation["quota"] = np.minimum(
                    allocation.n, np.floor(allocation.n * (train_budget - len(stats)) / count) + 1
                ).astype(int)
                allocation["inclusion_probability"] = allocation.quota / allocation.n
                # Aggregate strata only; no observation rows in artifact metadata.
                import json

                manifest["partitions"][name]["strata_allocation"] = json.loads(
                    allocation.to_json(orient="records", date_format="iso")
                )
        return datasets, manifest
