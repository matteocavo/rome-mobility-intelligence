"""Anonymous read-only boundary: complete current population and paginated history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.contracts.public import (
    AggregateQuery,
    PageQuery,
    PredictionAggregate,
    PredictionPage,
    RouteCatalog,
    RouteGeometry,
    RouteMapQuery,
)
from app.data.databricks_client import QueryTimeoutError
from app.persistence.database import DatabaseTimeout
from app.services.public_summary import NetworkSummary

router = APIRouter(prefix="/public", tags=["Public persisted data"])


def _validated(request: Request, schema):
    if any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, "Duplicate query parameters are not supported")
    try:
        return schema.model_validate(dict(request.query_params))
    except ValidationError:
        raise HTTPException(422, "Public query schema is invalid") from None


def parameters(request: Request) -> PageQuery:
    return _validated(request, PageQuery)


def aggregate_parameters(request: Request) -> AggregateQuery:
    return _validated(request, AggregateQuery)


def no_parameters(request: Request):
    if request.query_params:
        raise HTTPException(422, "Query parameters are not supported")


def network_read(request):
    try:
        return request.app.state.public_population.summary()
    except QueryTimeoutError:
        raise HTTPException(504, "Current scoring summary timeout") from None
    except Exception:
        raise HTTPException(503, "Current scoring summary temporarily unavailable") from None


@router.get("/status", response_model=NetworkSummary, dependencies=[Depends(no_parameters)])
def status(request: Request):
    return network_read(request)


@router.get("/summary", response_model=NetworkSummary, dependencies=[Depends(no_parameters)])
def summary(request: Request):
    return network_read(request)


@router.get("/predictions/current", response_model=PredictionPage)
def current(request: Request, query: Annotated[PageQuery, Depends(parameters)]):
    return page_read(request, "current", query)


@router.get("/predictions/history", response_model=PredictionPage)
def history(request: Request, query: Annotated[PageQuery, Depends(parameters)]):
    return page_read(request, "history", query)


@router.get("/predictions/current/aggregate", response_model=PredictionAggregate)
def current_aggregate(
    request: Request, query: Annotated[AggregateQuery, Depends(aggregate_parameters)]
):
    return page_read(request, "current", query, "aggregate")


@router.get("/predictions/history/aggregate", response_model=PredictionAggregate)
def history_aggregate(
    request: Request, query: Annotated[AggregateQuery, Depends(aggregate_parameters)]
):
    return page_read(request, "history", query, "aggregate")


def page_read(request, kind, query, operation="page"):
    try:
        service = (
            request.app.state.public_population
            if kind == "current"
            else request.app.state.public_history
        )
        return getattr(service, operation)(query)
    except (DatabaseTimeout, QueryTimeoutError):
        raise HTTPException(504, "Public data query timeout") from None
    except ValueError:
        raise HTTPException(422, "Public query or source contract is invalid") from None
    except Exception:
        raise HTTPException(503, "Public data temporarily unavailable") from None


@router.get("/routes", response_model=RouteCatalog, dependencies=[Depends(no_parameters)])
def routes(request: Request):
    return request.app.state.public_history.geography.catalog


@router.get("/route-map", response_model=RouteGeometry)
def route_map(request: Request):
    if any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise HTTPException(422, "Duplicate query parameters are not supported")
    try:
        query = RouteMapQuery.model_validate(dict(request.query_params))
    except ValidationError:
        raise HTTPException(422, "Public map query schema is invalid") from None
    try:
        return request.app.state.public_history.geography.route_map(query.route, query.trip)
    except Exception:
        raise HTTPException(503, "Static GTFS map temporarily unavailable") from None
