import pyodbc
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from autotuner_api.config import Settings
from autotuner_api.errors import invalid_request_handler
from autotuner_api.routes.collections import router as collection_router
from autotuner_api.routes.health import router as health_router
from autotuner_api.routes.targets import router as target_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Compose the application without opening database connections."""
    app = FastAPI(
        title="Automated Database Tuner",
        version="0.1.0",
    )

    app.state.settings = settings if settings is not None else Settings.load()

    app.add_exception_handler(
        RequestValidationError,
        invalid_request_handler,
    )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(target_router, prefix="/api/v1")
    app.include_router(collection_router, prefix="/api/v1")

    @app.exception_handler(pyodbc.Error)
    async def repository_error(request, error):
        return JSONResponse(status_code=503, content={"detail": "Repository unavailable. Check the repository connection and SQL migrations."})

    return app
