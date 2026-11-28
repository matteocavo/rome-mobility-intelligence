"""Public Gold analytics. No scoring, writes, warehouse start or automatic retry."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.contracts.analytics import AnalyticsQuery, AnalyticsResponse

router = APIRouter(prefix="/public/analytics", tags=["Observed historical analytics"])
logger = logging.getLogger(__name__)


@router.get("/observed", response_model=AnalyticsResponse)
def observed(request: Request):
    if any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, "Duplicate analytics parameters")
    try:
        query = AnalyticsQuery.model_validate(dict(request.query_params))
    except ValueError:
        raise HTTPException(422, "Unsupported analytics filters or period") from None
    try:
        return request.app.state.historical_analytics.get(query)
    except Exception:
        logger.warning("gold_analytics_unavailable")
        raise HTTPException(503, "Observed Gold analytics temporarily unavailable") from None
