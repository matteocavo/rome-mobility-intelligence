"""Stateless operational inference. No client-controlled SQL or model settings."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.contracts.inference import (
    BatchPredictRequest,
    BatchPredictResponse,
    CurrentPredictionsResponse,
    PredictionResponse,
    PredictRequest,
)
from app.data.databricks_client import DataAccessError, QueryTimeoutError
from app.services.current_scoring import CurrentScoringService
from app.services.model_service import ModelService

router = APIRouter()
logger = logging.getLogger(__name__)
ERRORS = {
    400: {"description": "Semantically invalid input"},
    413: {"description": "Batch exceeds configured limit"},
    422: {"description": "Invalid schema or feature contract"},
    503: {"description": "Model or scoring source unavailable"},
    504: {"description": "Databricks query deadline exceeded"},
}


def operational_model(request: Request):
    if request.url.path in {"/predict", "/predict/batch"} and request.query_params:
        raise HTTPException(422, "Prediction endpoints do not accept query parameters")
    model = request.app.state.model
    test_mode = request.app.state.settings.environment == "test"
    if model is None or (model.metadata.synthetic and not test_mode):
        raise HTTPException(503, "Operational model is not ready")
    return model


def infer(model, records):
    try:
        return model.predict_batch(records)
    except (ValueError, TypeError):
        logger.warning("inference_contract_rejected")
        raise HTTPException(422, "Feature contract is invalid") from None
    except Exception:
        logger.error("inference_unavailable")
        raise HTTPException(503, "Inference temporarily unavailable") from None


@router.post("/predict", response_model=PredictionResponse, responses=ERRORS)
def predict(
    body: PredictRequest,
    request: Request,
    model: Annotated[ModelService, Depends(operational_model)],
):
    return {**model.identity(), **infer(model, [body.model_dump()])[0]}


@router.post("/predict/batch", response_model=BatchPredictResponse, responses=ERRORS)
def predict_batch(
    body: BatchPredictRequest,
    request: Request,
    model: Annotated[ModelService, Depends(operational_model)],
):
    if len(body.root) > request.app.state.settings.inference_max_batch_rows:
        raise HTTPException(413, "Batch exceeds configured row limit")
    if not body.root:
        raise HTTPException(400, "Batch must contain at least one observation")
    predictions = infer(model, [row.model_dump() for row in body.root])
    return {**model.identity(), "rows": len(predictions), "predictions": predictions}


class CurrentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=50, ge=1, le=100)


def current_query(request: Request) -> CurrentQuery:
    # Reject unknown and duplicate keys rather than silently ignoring overrides.
    if any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, "Duplicate query parameters are not supported")
    try:
        query = CurrentQuery.model_validate(dict(request.query_params))
    except ValidationError:
        raise HTTPException(422, "Only a bounded limit query parameter is accepted") from None
    if "limit" not in request.query_params:
        query.limit = min(50, request.app.state.settings.inference_max_batch_rows)
    if query.limit > request.app.state.settings.inference_max_batch_rows:
        raise HTTPException(422, "Limit exceeds configured row limit")
    return query


@router.get(
    "/predictions/current",
    response_model=CurrentPredictionsResponse,
    responses=ERRORS,
    openapi_extra={
        "parameters": [
            {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
            }
        ]
    },
)
def current(
    request: Request,
    query: Annotated[CurrentQuery, Depends(current_query)],
    model: Annotated[ModelService, Depends(operational_model)],
):
    try:
        return (
            CurrentScoringService(request.app.state.current_repository, model)
            .score(query.limit)
            .response
        )
    except QueryTimeoutError:
        logger.warning("current_scoring_deadline")
        raise HTTPException(504, "Scoring query deadline exceeded") from None
    except DataAccessError:
        logger.warning("current_scoring_unavailable")
        raise HTTPException(503, "Scoring source temporarily unavailable") from None
    except (ValueError, TypeError, KeyError):
        logger.warning("current_scoring_contract_rejected")
        raise HTTPException(422, "Current scoring snapshot is invalid") from None
    except Exception:
        logger.error("current_scoring_unavailable")
        raise HTTPException(503, "Scoring source temporarily unavailable") from None
