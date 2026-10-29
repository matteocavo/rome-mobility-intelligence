"""Fixed SELECT over the latest scoring feed; never accepts client SQL/identifiers."""

import pandas as pd

from app.contracts.inference import PredictRequest
from app.contracts.operational_ml import CONTRACT, FEATURES, HASH, KEY
from app.core.config import Settings
from app.data.databricks_client import DataAccessError, DatabricksClient, identifier

TABLE = "`rome_transport`.`features`.`next_stop_delay_scoring`"


class CurrentScoringRepository:
    def __init__(self, client: DatabricksClient, settings: Settings):
        self.client, self.settings = client, settings

    def latest(self, limit: int) -> pd.DataFrame:
        if type(limit) is not int or not 1 <= limit <= self.settings.inference_max_batch_rows:
            raise ValueError("Invalid scoring limit")
        return self._latest(limit, self.settings.inference_max_bytes)

    def population(self) -> pd.DataFrame:
        # Fixed server budget; never a browser-supplied limit or a truncated population.
        frame = self._latest(50000, 48_000_000, allow_empty=True)
        if frame.empty:
            return frame
        if not frame.snapshot_rows.eq(len(frame)).all():
            raise DataAccessError("Current population exceeds the serving budget")
        return frame

    def _latest(self, limit, max_bytes, *, allow_empty=False):
        columns = ", ".join(identifier(x) for x in CONTRACT["inference"]["columns"])
        grain = ", ".join(identifier(x) for x in KEY)
        # Windows inspect lineage across the whole latest feed, before LIMIT.
        audits = []
        for name in (
            "feature_contract_hash",
            "source_silver_version",
            "feature_preparation_batch_id",
            "feature_prepared_at",
        ):
            for operation in ("MIN", "MAX", "COUNT"):
                audits.append(
                    f"{operation}({identifier(name)}) OVER () AS {name}_{operation.lower()}"
                )
        query = f"""SELECT {columns}, {", ".join(audits)},
            COUNT(*) OVER () AS snapshot_rows,
            COUNT(*) OVER (PARTITION BY {grain}) AS grain_rows
            FROM {TABLE}
            WHERE feed_timestamp = (SELECT MAX(feed_timestamp) FROM {TABLE})
            ORDER BY {grain} LIMIT :requested_limit"""
        frame = self.client.select(
            query,
            {"requested_limit": limit},
            max_rows=limit,
            max_bytes=max_bytes,
            **({"compact_strings": True} if allow_empty else {}),
        )
        if frame.empty and allow_empty:
            return frame
        if frame.empty:
            raise ValueError("No current scoring input available")
        if frame[list(KEY)].isna().any().any() or not frame.grain_rows.eq(1).all():
            raise ValueError("Invalid scoring grain")
        if frame.feed_timestamp.nunique() != 1 or not frame.feature_contract_hash.eq(HASH).all():
            raise ValueError("Invalid scoring contract")
        for name in (
            "feature_contract_hash",
            "source_silver_version",
            "feature_preparation_batch_id",
            "feature_prepared_at",
        ):
            if not frame[f"{name}_count"].eq(frame.snapshot_rows).all():
                raise ValueError("Missing snapshot lineage")
            if not frame[f"{name}_min"].eq(frame[f"{name}_max"]).all():
                raise ValueError("Ambiguous snapshot lineage")
        if not frame.target_next_stop_sequence.gt(frame.stop_sequence).all():
            raise ValueError("Invalid next-stop identity")
        now = pd.Timestamp.now(tz="UTC")
        feed = pd.to_numeric(frame.feed_timestamp, errors="raise")
        prepared = pd.to_datetime(frame.feature_prepared_at, utc=True, errors="raise")
        if (feed > now.timestamp()).any() or (feed < 0).any() or (prepared > now).any():
            raise ValueError("Future or invalid scoring watermark")
        # Validate only the explicit 47-feature projection, never identifiers or targets.
        # Stream validation: never materialize N x 47 boxed values/dicts at once.
        for values in frame.loc[:, list(FEATURES)].itertuples(index=False, name=None):
            clean = {
                key: None if pd.isna(value) else value
                for key, value in zip(FEATURES, values, strict=True)
            }
            PredictRequest.model_validate(clean)
        return frame
