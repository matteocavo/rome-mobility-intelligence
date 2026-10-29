"""Small server-side aggregates over the complete latest scoring feed, never a UI slice."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.contracts.inference import ClosedSchema


class RouteRisk(ClosedSchema):
    route_id: str
    route_type: int | None
    scored_count: int = Field(ge=1)
    major_delay_count: int = Field(ge=0)
    major_delay_rate: float = Field(ge=0, le=1)


class NetworkSummary(ClosedSchema):
    status: Literal["ok", "no_data"] = "ok"
    coverage: str = "current_scoring_population"
    query_generated_at: datetime
    source_watermark: datetime | None
    source_age_seconds: float | None
    scored_count: int = Field(ge=0)
    route_count: int = Field(ge=0)
    observed_delay_count: int = Field(ge=0)
    median_observed_delay_seconds: float | None
    p90_observed_delay_seconds: float | None
    observed_delay_distribution: dict[str, int]
    critical_routes: list[RouteRisk] = Field(default_factory=list, max_length=5)
    major_delay_count: int = Field(ge=0)
    major_delay_rate: float | None = Field(ge=0, le=1)
    risk_status: Literal["complete_operational_model_population", "no_current_observations"]
