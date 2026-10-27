"""HTTP schemas generated from the pinned, ordered raw-feature contract."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, RootModel, create_model

from app.contracts.operational_ml import CATEGORICAL, NUMERIC


class ClosedSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]
fields = {name: (FiniteNumber | None, ...) for name in NUMERIC}
fields.update(
    {
        name: (int | None if name in {"route_type", "direction_id"} else str | None, ...)
        for name in CATEGORICAL
    }
)
PredictRequest = create_model("PredictRequest", __base__=ClosedSchema, **fields)


class BatchPredictRequest(RootModel[list[PredictRequest]]):
    pass


class Prediction(ClosedSchema):
    major_delay_probability: float = Field(ge=0, le=1)
    predicted_major_delay: bool


class ModelIdentity(ClosedSchema):
    model_version: str
    feature_contract_hash: str
    threshold: float


class PredictionResponse(ModelIdentity, Prediction):
    pass


class BatchPredictResponse(ModelIdentity):
    rows: int
    predictions: list[Prediction]


class CurrentPrediction(Prediction):
    route_id: str | None
    trip_id: str | None
    vehicle_id: str | None
    stop_id: str | None
    feed_timestamp: int
    current_arrival_delay_seconds: float | None
    threshold: float


class CurrentPredictionsResponse(ModelIdentity):
    source_watermark: datetime
    prediction_generated_at: datetime
    source_age_seconds: float = Field(ge=0)
    rows: int
    predictions: list[CurrentPrediction]
