from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only; does not assert SQL Server connectivity."""
    return HealthResponse(status="ok", service="autotuner-api")
