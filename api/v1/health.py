"""Health check endpoints - Version 1."""

from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from memory.database import get_session

router = APIRouter()


class ServiceStatus(BaseModel):
    """Status of an individual service"""
    available: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Complete health check response"""
    status: str  # healthy, degraded, unhealthy
    version: str
    timestamp: str
    uptime_seconds: Optional[int] = None
    services: Dict[str, ServiceStatus]


# Track startup time
_startup_time = datetime.utcnow()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint.

    Checks:
    - Database connectivity (PostgreSQL)
    - Overall system status

    Returns:
        200 OK: All services healthy
        503 Service Unavailable: One or more services down
    """
    services: Dict[str, ServiceStatus] = {}
    overall_healthy = True

    # Check database
    try:
        start = datetime.utcnow()
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        latency = (datetime.utcnow() - start).total_seconds() * 1000

        services["database"] = ServiceStatus(
            available=True,
            latency_ms=round(latency, 2)
        )
    except Exception as e:
        services["database"] = ServiceStatus(
            available=False,
            error=str(e)
        )
        overall_healthy = False

    # Determine overall status
    if overall_healthy:
        overall_status = "healthy"
        http_status = status.HTTP_200_OK
    else:
        overall_status = "unhealthy"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    # Calculate uptime
    uptime = int((datetime.utcnow() - _startup_time).total_seconds())

    response = HealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat() + "Z",
        uptime_seconds=uptime,
        services=services,
    )

    return JSONResponse(
        status_code=http_status,
        content=response.model_dump(),
    )
