"""Manual scoring → minimal atomic application persistence; no Databricks writes."""

import logging

import pandas as pd

from app.contracts.history import PersistSummary, PredictionRecord
from app.persistence.database import DatabaseUnavailable

logger = logging.getLogger(__name__)


class BatchScoringService:
    def __init__(self, scoring, history, settings):
        self.scoring, self.history, self.settings = scoring, history, settings

    def run(self, limit: int) -> PersistSummary:
        if not self.settings.enable_prediction_persistence:
            raise DatabaseUnavailable("Prediction persistence disabled")
        if not 1 <= limit <= self.settings.inference_max_batch_rows:
            raise ValueError("Invalid persistence limit")
        logger.info("batch_scoring_started")
        scored = self.scoring.score(limit)
        response = scored.response
        records = []
        for prediction, (_, source) in zip(
            response.predictions, scored.frame.iterrows(), strict=True
        ):

            def optional(name, source=source):
                value = source.get(name)
                return None if pd.isna(value) else value

            records.append(
                PredictionRecord(
                    source_feed_timestamp=prediction.feed_timestamp,
                    prediction_generated_at=response.prediction_generated_at,
                    entity_id=source.entity_id,
                    route_id=prediction.route_id,
                    trip_id=prediction.trip_id,
                    vehicle_id=prediction.vehicle_id,
                    stop_id=prediction.stop_id,
                    stop_sequence=source.stop_sequence,
                    target_next_stop_id=optional("target_next_stop_id"),
                    current_arrival_delay_seconds=prediction.current_arrival_delay_seconds,
                    major_delay_probability=prediction.major_delay_probability,
                    predicted_major_delay=prediction.predicted_major_delay,
                    model_version=response.model_version,
                    feature_contract_hash=response.feature_contract_hash,
                    threshold=response.threshold,
                    source_silver_version=optional("source_silver_version"),
                    feature_preparation_batch_id=optional("feature_preparation_batch_id"),
                )
            )
        inserted = self.history.insert_batch(records)
        logger.info(
            "batch_scoring_completed evaluated=%d inserted=%d existing=%d",
            len(records),
            inserted,
            len(records) - inserted,
        )
        return PersistSummary(
            source_watermark=response.source_watermark,
            model_version=response.model_version,
            feature_contract_hash=response.feature_contract_hash,
            threshold=response.threshold,
            rows_evaluated=len(records),
            rows_inserted=inserted,
            rows_existing=len(records) - inserted,
        )
