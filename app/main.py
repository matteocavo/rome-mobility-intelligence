from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import health, inference, model
from app.core.config import Settings
from app.core.logging import configure_logging
from app.data.current_repository import CurrentScoringRepository
from app.data.databricks_client import DatabricksClient
from app.services.model_service import ModelService


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app):
        configure_logging()
        app.state.settings = cfg
        app.state.current_repository = CurrentScoringRepository(DatabricksClient(cfg), cfg)
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
        yield
        app.state.initialized = False

    application = FastAPI(title="Rome Mobility Intelligence", version="0.1.0", lifespan=lifespan)
    application.include_router(health.router)
    application.include_router(model.router)
    application.include_router(inference.router)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Pydantic's default includes rejected input values: never echo client secrets/paths.
        return JSONResponse(status_code=422, content={"detail": "Request schema is invalid"})

    return application


app = create_app()
