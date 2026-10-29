"""Explicit browser allowlist. No model artifacts, lineage IDs or raw feature vectors."""

from datetime import datetime
from math import ceil
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.contracts.inference import ClosedSchema


class PublicPrediction(ClosedSchema):
    trip_id: str | None = Field(default=None, max_length=512)
    vehicle_id: str | None = Field(default=None, max_length=512)
    route_type: int | None = None
    route_short_name: str | None = None
    stop_name: str | None = None
    stop_lat: float | None = Field(default=None, ge=-90, le=90)
    stop_lon: float | None = Field(default=None, ge=-180, le=180)
    vehicle_lat: float | None = None
    vehicle_lon: float | None = None
    observation_id: str
    route_id: str | None = Field(default=None, max_length=512)
    stop_id: str = Field(min_length=1, max_length=512)
    stop_sequence: int = Field(ge=0)
    target_next_stop_id: str | None = Field(default=None, max_length=512)
    observed_current_delay_seconds: float | None = None
    major_delay_probability: float = Field(ge=0, le=1)
    predicted_major_delay: bool
    threshold: float = Field(gt=0, lt=1)
    source_watermark: datetime
    prediction_generated_at: datetime


class PageQuery(ClosedSchema):
    page: int = Field(default=1, ge=1, le=100000)
    page_size: Literal[10, 20, 50] = 20
    route: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    stop: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    query: str = Field(default="", max_length=100, pattern=r"^[^\x00-\x1f\x7f]*$")
    mode: Literal["all", "bus", "tram"] = "all"
    risk_class: Literal["all", "major", "moderate", "regular"] = "all"
    sort: Literal["risk_desc", "delay_desc", "route_asc", "time_desc"] = "risk_desc"
    from_at: datetime | None = Field(default=None, alias="from")
    to_at: datetime | None = Field(default=None, alias="to")

    @field_validator("page_size", mode="before")
    @classmethod
    def parse_page_size(cls, value):
        return int(value) if isinstance(value, str) and value.isdecimal() else value

    @model_validator(mode="after")
    def validate_range(self):
        for value in (self.from_at, self.to_at):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Timezone required")
        if self.from_at and self.to_at and self.from_at > self.to_at:
            raise ValueError("Invalid time range")
        return self


class PredictionPage(ClosedSchema):
    coverage: Literal["current_scoring_population", "persisted_prediction_history"]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: Literal[10, 20, 50]
    total_pages: int = Field(ge=1)
    source_watermark: datetime | None
    source_age_seconds: float | None
    query_generated_at: datetime
    items: list[PublicPrediction]
    population_generated_at: datetime | None = None


def page_response(query, *, total, items, coverage, watermark, now, generated=None):
    return PredictionPage(
        coverage=coverage,
        total=total,
        page=query.page,
        page_size=query.page_size,
        total_pages=max(1, ceil(total / query.page_size)),
        source_watermark=watermark,
        source_age_seconds=(now - watermark).total_seconds() if watermark else None,
        query_generated_at=now,
        items=items,
        population_generated_at=generated,
    )
