from fastapi import FastAPI

from autotuner_api.config import Settings
from autotuner_api.routes.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Compose the application without opening database connections."""
    app = FastAPI(title="Automated Database Tuner", version="0.1.0")
    app.state.settings = settings if settings is not None else Settings.load()
    app.include_router(health_router, prefix="/api/v1")
    return app
