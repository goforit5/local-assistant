"""API v1 router aggregator."""

from fastapi import APIRouter
from api.v1 import documents, vendors, health

router = APIRouter()

# Include all v1 routers
router.include_router(health.router, tags=["health"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
