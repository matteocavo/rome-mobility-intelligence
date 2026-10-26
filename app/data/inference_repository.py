import pandas as pd

from app.contracts.operational_ml import CONTRACT, FEATURES, HASH, KEY
from app.core.config import Settings
from app.data.databricks_client import DatabricksClient, identifier, table_name
from app.ml.preprocessing import FeatureValidator


class InferenceRepository:
    def __init__(self, client: DatabricksClient, settings: Settings):
        self.client, self.settings = client, settings

    def snapshot(
        self,
        *,
        version: int,
        feed: int,
        expected_rows: int,
        max_age_seconds: int,
        max_bytes: int = 64_000_000,
    ) -> pd.DataFrame:
        if any(type(x) is not int or x < 0 for x in (version, feed, expected_rows)):
            raise ValueError("Explicit pinned version, feed and count required")
        if expected_rows < 1 or max_age_seconds < 1:
            raise ValueError("Positive count and explicitly approved freshness limit required")
        columns = ", ".join(identifier(x) for x in CONTRACT["inference"]["columns"])
        table = table_name(self.settings, self.settings.inference_table)
        frame = self.client.select(
            f"SELECT {columns} FROM {table} VERSION AS OF {version} WHERE feed_timestamp=:feed",
            {"feed": feed},
            max_rows=expected_rows,
            max_bytes=max_bytes,
        )
        if len(frame) != expected_rows or frame[list(KEY)].isna().any().any():
            raise ValueError("Incomplete scoring snapshot")
        if frame.duplicated(list(KEY)).any() or not frame.feature_contract_hash.eq(HASH).all():
            raise ValueError("Invalid scoring grain or hash")
        if not frame.target_next_stop_sequence.gt(frame.stop_sequence).all():
            raise ValueError("Invalid next-stop identity")
        now = pd.Timestamp.now(tz="UTC")
        prepared = pd.to_datetime(frame.feature_prepared_at, utc=True, errors="raise")
        age = now.timestamp() - feed
        if age < 0 or age > max_age_seconds or prepared.isna().any():
            raise ValueError("Stale or future scoring source")
        if (prepared > now).any() or ((now - prepared).dt.total_seconds() > max_age_seconds).any():
            raise ValueError("Stale or future preparation")
        for name in CONTRACT["inference"]["lineage_columns"]:
            if frame[name].isna().any() or frame[name].nunique() != 1:
                raise ValueError("Ambiguous preparation lineage")
        if frame.feed_timestamp.nunique() != 1:
            raise ValueError("Multiple feed epochs")
        FeatureValidator().transform(frame[list(FEATURES)])
        return frame
