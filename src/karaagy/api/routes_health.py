"""Health check and liveness endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = "ok"
    service: str = "karaagy"


@router.get("/healthz", response_model=HealthStatus)
@router.get("/v1/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """Return service health status."""
    return HealthStatus(status="ok", service="karaagy")
