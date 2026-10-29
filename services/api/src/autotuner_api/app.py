from contextlib import asynccontextmanager
import asyncio
from autotuner_api.simulator import SimulationManager
from autotuner_api.routes.candidates import router as candidate_router
from autotuner_api.routes.cleanup import router as cleanup_router
from autotuner_api.routes.simulator import router as simulator_router
import pyodbc
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from autotuner_api.config import Settings
from autotuner_api.errors import invalid_request_handler
from autotuner_api.routes.collections import router as collection_router
from autotuner_api.routes.health import router as health_router
from autotuner_api.routes.targets import router as target_router
from autotuner_api.routes.recommendations import router as recommendation_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Compose the application without opening database connections."""
    manager = SimulationManager()

    @asynccontextmanager
    async def lifespan(app):
        yield
        await asyncio.to_thread(manager.shutdown)

    app = FastAPI(
        lifespan=lifespan,
        title="Automated Database Tuner",
        version="0.1.0",
    )

    app.state.simulator = manager
    app.state.settings = settings if settings is not None else Settings.load()

    app.add_exception_handler(
        RequestValidationError,
        invalid_request_handler,
    )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(target_router, prefix="/api/v1")
    app.include_router(collection_router, prefix="/api/v1")
    app.include_router(recommendation_router, prefix="/api/v1")

    app.include_router(candidate_router, prefix="/api/v1")
    app.include_router(cleanup_router, prefix="/api/v1")
    app.include_router(simulator_router, prefix="/api/v1")

    @app.exception_handler(pyodbc.Error)
    async def repository_error(request, error):
        return JSONResponse(status_code=503, content={"detail": "Repository unavailable. Check the repository connection and SQL migrations."})

    return app
