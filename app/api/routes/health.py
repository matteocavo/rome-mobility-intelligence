from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.core.service_auth import SERVICE_HEADER, ServiceAuthError, verify_service_key
from app.core.workload_auth import WorkloadAuthenticationError, WorkloadCredentials

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "rome-mobility-intelligence", "version": __version__}


@router.get("/ready")
def ready(request: Request):
    state = request.app.state
    available = state.initialized and state.model is not None and not state.model_error
    if (
        state.model is not None
        and state.model.metadata.synthetic
        and state.settings.environment != "test"
    ):
        available = False
    key = request.headers.get(SERVICE_HEADER)
    if key is None:
        return JSONResponse(
            status_code=200 if available else 503,
            content={"status": "ready" if available else "not_ready"},
        )
    try:
        verify_service_key(state.settings, key)
    except ServiceAuthError as error:
        raise HTTPException(error.status, str(error)) from None
    try:
        WorkloadCredentials(state.settings)  # Configuration only: no OAuth or SQL traffic.
        identity_configured = True
    except WorkloadAuthenticationError:
        identity_configured = False
    return JSONResponse(
        status_code=200 if available else 503,
        content={
            "status": "ready" if available else "not_ready",
            "model_status": "unavailable"
            if state.model_error
            else ("loaded" if state.model else "not_configured"),
            "mode": "model" if state.model else "skeleton",
            "model_ready": available,
            "artifact_integrity": "verified" if available else "not_verified",
            "workload_identity_configured": identity_configured,
            "databricks_readiness": "not_checked",
            "database_configured": state.database.configured,
            "prediction_persistence_enabled": state.settings.enable_prediction_persistence,
        },
    )
