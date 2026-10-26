from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "rome-mobility-intelligence", "version": "0.1.0"}


@router.get("/ready")
def ready(request: Request):
    state = request.app.state
    available = state.initialized and not state.model_error
    return JSONResponse(
        status_code=200 if available else 503,
        content={
            "status": "ready" if available else "not_ready",
            "model_status": "unavailable"
            if state.model_error
            else ("loaded" if state.model else "not_configured"),
            "mode": "model" if state.model else "skeleton",
        },
    )
