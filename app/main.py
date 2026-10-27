from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import health, history, inference, model
from app.core.config import Settings
from app.core.deployment import validate_deployment
from app.core.http_security import HttpSecurity
from app.core.logging import configure_logging
from app.core.service_auth import require_service_key
from app.data.current_repository import CurrentScoringRepository
from app.data.databricks_client import DatabricksClient
from app.persistence.database import Database
from app.persistence.history_repository import PredictionHistoryRepository
from app.services.model_service import ModelService


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings if settings is not None else Settings()
    validate_deployment(cfg)

    @asynccontextmanager
    async def lifespan(app):
        configure_logging()
        app.state.settings = cfg
        app.state.current_repository = CurrentScoringRepository(DatabricksClient(cfg), cfg)
        app.state.database = Database(cfg)
        app.state.history_repository = PredictionHistoryRepository(app.state.database, cfg)
        app.state.model = None
        app.state.model_error = False
        app.state.initialized = False
        if cfg.model_artifact_path:
            try:
                app.state.model = ModelService(
                    cfg.model_artifact_path,
                    trusted_root=cfg.model_artifact_root,
                    expected_manifest_sha256=cfg.model_artifact_manifest_sha256,
                )
            except Exception:
                app.state.model_error = True
        app.state.initialized = True
        try:
            yield
        finally:
            app.state.database.dispose()
            app.state.initialized = False

    production = cfg.environment == "production"
    application = FastAPI(
        title="Rome Mobility Intelligence",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        redirect_slashes=False,
    )
    application.include_router(health.router)
    service_auth = [Depends(require_service_key)]
    application.include_router(model.router, dependencies=service_auth)
    application.include_router(inference.router, dependencies=service_auth)
    application.include_router(history.router, dependencies=service_auth)
    if cfg.cors_allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )
    application.add_middleware(HttpSecurity, cfg=cfg)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Pydantic's default includes rejected input values: never echo client secrets/paths.
        return JSONResponse(status_code=422, content={"detail": "Request schema is invalid"})

    return application


app = create_app()
