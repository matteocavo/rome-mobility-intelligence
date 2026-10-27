"""Manual/internal persistence trigger and bounded, read-only application history."""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.api.routes.inference import ERRORS, CurrentQuery, current_query, operational_model
from app.contracts.history import HistoryQuery, HistoryResponse, PersistSummary
from app.data.databricks_client import DataAccessError, QueryTimeoutError
from app.persistence.database import DatabaseTimeout, DatabaseUnavailable
from app.services.batch_scoring import BatchScoringService
from app.services.current_scoring import CurrentScoringService
from app.services.model_service import ModelService

router = APIRouter()
logger = logging.getLogger(__name__)


async def persistence_enabled(request: Request):
    if not request.app.state.settings.enable_prediction_persistence:
        raise HTTPException(503, "Prediction persistence is disabled")
    if not request.app.state.database.configured:
        raise HTTPException(503, "Application database is not configured")
    async for chunk in request.stream():
        if chunk:
            raise HTTPException(422, "Only a bounded limit query parameter is accepted")


@router.post(
    "/predictions/current/persist",
    response_model=PersistSummary,
    responses=ERRORS,
    dependencies=[Depends(persistence_enabled)],
    description="Manual/local/internal trigger. Disabled by default; not Internet-ready.",
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
def persist_current(
    request: Request,
    query: Annotated[CurrentQuery, Depends(current_query)],
    model: Annotated[ModelService, Depends(operational_model)],
):
    service = BatchScoringService(
        CurrentScoringService(request.app.state.current_repository, model),
        request.app.state.history_repository,
        request.app.state.settings,
    )
    try:
        return service.run(query.limit)
    except (DatabaseTimeout, QueryTimeoutError):
        logger.warning("persistence_query_timeout")
        raise HTTPException(504, "Prediction persistence query timeout") from None
    except (DatabaseUnavailable, DataAccessError):
        logger.warning("persistence_unavailable")
        raise HTTPException(503, "Prediction persistence temporarily unavailable") from None
    except (ValueError, TypeError, KeyError):
        logger.warning("persistence_contract_rejected")
        raise HTTPException(422, "Current scoring contract is invalid") from None
    except Exception:
        logger.error("persistence_unavailable")
        raise HTTPException(503, "Prediction persistence temporarily unavailable") from None


def history_query(request: Request) -> HistoryQuery:
    if any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, "Duplicate query parameters are not supported")
    try:
        query = HistoryQuery.model_validate(dict(request.query_params))
    except ValidationError:
        raise HTTPException(422, "History filter schema is invalid") from None
    maximum = request.app.state.settings.history_max_rows
    if "limit" not in request.query_params:
        query.limit = min(50, maximum)
    if query.limit > maximum:
        raise HTTPException(422, "History row limit exceeded")
    try:
        query.bounded_range(request.app.state.settings.history_max_range_days)
    except OverflowError:
        raise HTTPException(413, "History time range exceeds configured maximum") from None
    except ValueError:
        raise HTTPException(400, "History start must precede end") from None
    return query


@router.get(
    "/predictions/history",
    response_model=HistoryResponse,
    responses=ERRORS,
    openapi_extra={
        "parameters": [
            {"name": "route_id", "in": "query", "schema": {"type": "string"}},
            {"name": "from", "in": "query", "schema": {"type": "string", "format": "date-time"}},
            {"name": "to", "in": "query", "schema": {"type": "string", "format": "date-time"}},
            {
                "name": "limit",
                "in": "query",
                "schema": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
            {"name": "predicted_major_delay", "in": "query", "schema": {"type": "boolean"}},
        ]
    },
)
def history(request: Request, query: Annotated[HistoryQuery, Depends(history_query)]):
    try:
        records = request.app.state.history_repository.history(query)
    except DatabaseTimeout:
        logger.warning("history_query_timeout")
        raise HTTPException(504, "History query timeout") from None
    except Exception:
        logger.warning("history_database_unavailable")
        raise HTTPException(503, "History database temporarily unavailable") from None
    return HistoryResponse(
        rows=len(records), query_generated_at=datetime.now(timezone.utc), predictions=records
    )
