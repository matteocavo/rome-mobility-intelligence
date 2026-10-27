"""Shared source → validated features → inference path for preview and persistence."""

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from app.contracts.inference import CurrentPredictionsResponse, PredictRequest
from app.contracts.operational_ml import FEATURES


class InvalidScoringInput(ValueError):
    pass


@dataclass
class ScoredSnapshot:
    frame: pd.DataFrame
    response: CurrentPredictionsResponse


class CurrentScoringService:
    def __init__(self, repository, model):
        self.repository, self.model = repository, model

    def score(self, limit: int) -> ScoredSnapshot:
        frame = self.repository.latest(limit)
        try:
            if frame.empty or len(frame) > limit:
                raise ValueError("Invalid snapshot size")
            rows = [
                PredictRequest.model_validate(
                    {k: None if pd.isna(v) else v for k, v in row.items()}
                ).model_dump()
                for row in frame[list(FEATURES)].to_dict("records")
            ]
            watermark = datetime.fromtimestamp(int(frame.feed_timestamp.iloc[0]), timezone.utc)
            if watermark > datetime.now(timezone.utc):
                raise ValueError("Future watermark")
        except (ValueError, TypeError, KeyError, OverflowError):
            raise InvalidScoringInput("Current scoring feature contract is invalid") from None
        predictions = self.model.predict_batch(rows)
        generated = datetime.now(timezone.utc)
        for result, (_, source) in zip(predictions, frame.iterrows(), strict=True):
            for name in ("route_id", "trip_id", "vehicle_id", "stop_id"):
                value = source.get(name)
                result[name] = None if pd.isna(value) else str(value)
            delay = source.get("current_arrival_delay_seconds")
            result.update(
                feed_timestamp=int(source.feed_timestamp),
                threshold=self.model.threshold,
                current_arrival_delay_seconds=None if pd.isna(delay) else float(delay),
            )
        response = CurrentPredictionsResponse(
            **self.model.identity(),
            source_watermark=watermark,
            prediction_generated_at=generated,
            source_age_seconds=(generated - watermark).total_seconds(),
            rows=len(predictions),
            predictions=predictions,
        )
        return ScoredSnapshot(frame, response)
