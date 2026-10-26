from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, model
from app.core.config import Settings
from app.core.logging import configure_logging
from app.services.model_service import ModelService


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app):
        configure_logging()
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
    return application


app = create_app()
