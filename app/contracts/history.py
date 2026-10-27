"""Typed application history input/response; no raw feature vectors or client identities."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import ConfigDict, Field, field_validator

from app.contracts.inference import ClosedSchema, ModelIdentity, Prediction

OperationalId = Annotated[str, Field(min_length=1, max_length=512)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class PredictionRecord(Prediction):
    source_feed_timestamp: int = Field(ge=0)
    prediction_generated_at: datetime
    entity_id: OperationalId
    route_id: OperationalId | None = None
    trip_id: OperationalId
    vehicle_id: OperationalId | None = None
    stop_id: OperationalId
    stop_sequence: int = Field(ge=0)
    target_next_stop_id: OperationalId | None = None
    current_arrival_delay_seconds: float | None = None
    model_version: Digest
    feature_contract_hash: Digest
    threshold: float = Field(gt=0, lt=1)
    source_silver_version: int | None = Field(default=None, ge=0)
    feature_preparation_batch_id: OperationalId | None = None

    @field_validator("prediction_generated_at")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value.astimezone(timezone.utc)


class HistoryRecord(PredictionRecord):
    id: int
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_utc(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value.astimezone(timezone.utc)


class HistoryResponse(ClosedSchema):
    rows: int
    query_generated_at: datetime
    predictions: list[HistoryRecord]


class PersistSummary(ModelIdentity):
    source_watermark: datetime
    rows_evaluated: int
    rows_inserted: int
    rows_existing: int


class HistoryQuery(ClosedSchema):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)
    route_id: OperationalId | None = None
    from_time: datetime | None = Field(default=None, alias="from")
    to_time: datetime | None = Field(default=None, alias="to")
    limit: int = Field(default=50, ge=1, le=200)
    predicted_major_delay: bool | None = None

    @field_validator("from_time", "to_time")
    @classmethod
    def aware(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timezone-aware filter required")
            return value.astimezone(timezone.utc)
        return value

    def bounded_range(self, max_days: int, now: datetime | None = None):
        end = self.to_time or now or datetime.now(timezone.utc)
        start = self.from_time or end - timedelta(days=max_days)
        if start > end:
            raise ValueError("History start must precede end")
        if end - start > timedelta(days=max_days):
            raise OverflowError("History range exceeds configured maximum")
        return start, end
