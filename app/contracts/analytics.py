"""Observed Gold analytics, separate from all ML predictions and historical labels."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AnalyticsQuery(Closed):
    view: Literal["overview", "routes", "stops", "temporal"] = "overview"
    from_date: date | None = Field(default=None, alias="from")
    to_date: date | None = Field(default=None, alias="to")

    @model_validator(mode="after")
    def bounded(self):
        if self.view != "temporal" and (self.from_date or self.to_date):
            raise ValueError("Period filters apply only to temporal data")
        if bool(self.from_date) != bool(self.to_date):
            raise ValueError("Both dates required")
        if self.from_date and (
            self.to_date < self.from_date or (self.to_date - self.from_date).days > 30
        ):
            raise ValueError("At most 31 service dates")
        return self


class Metrics(Closed):
    total: int = Field(ge=0, strict=True)
    known: int = Field(ge=0, strict=True)
    missing: int = Field(ge=0, strict=True)
    major: int = Field(ge=0, strict=True)
    major_rate: float | None = Field(ge=0, le=1)
    mean_seconds: float | None
    median_seconds: float | None
    p90_seconds: float | None
    first_feed: datetime | None
    last_feed: datetime | None

    @model_validator(mode="after")
    def reconcile(self):
        if self.known + self.missing != self.total or self.major > self.known:
            raise ValueError("Counts do not reconcile")
        expected = self.major / self.known if self.known else None
        if self.major_rate != expected:
            raise ValueError("Known-delay denominator mismatch")
        if self.known == 0 and any(
            v is not None for v in (self.mean_seconds, self.median_seconds, self.p90_seconds)
        ):
            raise ValueError("Missing measurements must stay null")
        if self.total and (self.first_feed is None or self.last_feed is None):
            raise ValueError("Coverage required")
        if self.first_feed and self.last_feed and self.first_feed > self.last_feed:
            raise ValueError("Invalid coverage")
        return self


class AnalyticsItem(Metrics):
    key: str = Field(max_length=128)
    name: str | None = Field(default=None, max_length=512)
    service_date: date | None = None
    weekday: int | None = Field(default=None, ge=1, le=7)
    hour: int | None = Field(default=None, ge=0, le=23)


class CountBucket(Closed):
    key: str
    total: int = Field(ge=0)
    known: int = Field(ge=0)
    major: int = Field(ge=0)
    major_rate: float | None = Field(ge=0, le=1)


class AnalyticsResponse(Closed):
    coverage: Literal["gold_observed_history"] = "gold_observed_history"
    view: Literal["overview", "routes", "stops", "temporal"]
    release_id: str
    source_table: Literal["rome_transport.silver.realtime_enriched_observations"]
    source_version: int = Field(ge=0)
    scoring_version: int = Field(ge=0)
    gold_versions: dict[str, int]
    refreshed_at: datetime
    source_watermark: datetime
    query_generated_at: datetime
    metric_definition: Literal["reported_current_stop_arrival_delay_seconds"] = (
        "reported_current_stop_arrival_delay_seconds"
    )
    weighting: Literal["trip_stop_snapshot_observations"] = "trip_stop_snapshot_observations"
    timezone: Literal["Europe/Rome"] = "Europe/Rome"
    period_from: date | None = None
    period_to: date | None = None
    items: list[AnalyticsItem] = Field(max_length=744)
    daily: list[CountBucket] = Field(default_factory=list, max_length=31)
    hourly: list[CountBucket] = Field(default_factory=list, max_length=24)
    heatmap: list[CountBucket] = Field(default_factory=list, max_length=168)
