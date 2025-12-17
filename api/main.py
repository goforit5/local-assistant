"""Main FastAPI application."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator
import warnings

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from api.state import app_state
from api.routes import chat, vision, reasoning, computer, costs, health, documents, vendors, commitments, interactions  # , email - temporarily disabled due to OAuth config issue
from api.v1 import router as v1_router
from api.versions import API_VERSION, API_VERSIONS
from observability.metrics import get_metrics_collector
from observability.lifegraph_metrics import get_lifegraph_metrics
from providers.anthropic_provider import AnthropicProvider
from providers.openai_provider import OpenAIProvider
from providers.google_provider import GoogleProvider
from providers.base import ProviderConfig
from services.chat.router import ChatRouter

# Integration imports
from config.loader import ConfigLoader
from api.middleware.rate_limit import RateLimitMiddleware, get_redis_url
from lib.circuit_breaker import CircuitBreaker, CircuitBreakerConfig as CBConfig
from lib.cache import CacheManager
from api.openapi import custom_openapi
from api.middleware.metrics import PrometheusMiddleware
from api.errors import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
)

# Load environment variables from .env file (override any shell env vars)
load_dotenv(override=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and cleanup resources."""
    # Step 1: Initialize configuration loader (singleton)
    config = ConfigLoader.get_instance()
    app_state["config"] = config

    # Step 2: Initialize cache manager
    cache = CacheManager(redis_url=get_redis_url())
    await cache.initialize()
    app_state["cache"] = cache

    # Step 3: Initialize providers with ProviderConfig
    app_state["anthropic"] = AnthropicProvider(
        ProviderConfig(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    )
    app_state["openai"] = OpenAIProvider(
        ProviderConfig(api_key=os.getenv("OPENAI_API_KEY", ""))
    )
    app_state["google"] = GoogleProvider(
        ProviderConfig(api_key=os.getenv("GOOGLE_API_KEY", ""))
    )

    # Initialize provider clients
    await app_state["anthropic"].initialize()
    await app_state["openai"].initialize()
    await app_state["google"].initialize()

    # Step 4: Initialize circuit breakers for each provider
    circuit_breakers = {}
    for provider_name in ["anthropic", "openai", "google"]:
        cb_config = CBConfig(
            failure_threshold=5,
            failure_window=60,
            timeout=30,
            redis_url=get_redis_url()
        )
        cb = CircuitBreaker(provider_name, cb_config)
        await cb.initialize()
        circuit_breakers[provider_name] = cb
    app_state["circuit_breakers"] = circuit_breakers

    # Step 5: Initialize chat router
    app_state["chat_router"] = ChatRouter(
        primary=app_state["anthropic"],
        fallback=app_state["google"],
        strategy="capability_based"
    )

    yield

    # Cleanup
    await app_state["chat_router"].close()
    await app_state["anthropic"].close()
    await app_state["openai"].close()
    await app_state["google"].close()

    # Close circuit breakers
    for cb in circuit_breakers.values():
        await cb.close()

    # Close cache
    await cache.close()


app = FastAPI(
    title="Local Assistant API",
    description="Unicorn-grade AI assistant with vision, reasoning, and computer use",
    version=API_VERSION,
    lifespan=lifespan
)

# Enable custom OpenAPI metadata for enhanced documentation
app.openapi = lambda: custom_openapi(app)

# Add Prometheus metrics middleware (BEFORE CORS for complete coverage)
app.add_middleware(
    PrometheusMiddleware,
    exclude_paths=["/metrics", "/health", "/"]
)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    redis_url=get_redis_url(),
    config_path=None  # Uses config/rate_limits.yaml
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3001",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_versioning_middleware(request: Request, call_next):
    """Add API version headers and deprecation warnings."""
    response = await call_next(request)
    path = request.url.path

    # Add X-API-Version header to all v1 endpoints
    if path.startswith("/api/v1/"):
        response.headers["X-API-Version"] = "1.0.0"

    # Add deprecation warnings for legacy (unversioned) endpoints
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        # Skip deprecation for metrics, health (not versioned), and root
        if not any(path.startswith(p) for p in ["/metrics", "/api/health", "/"]):
            response.headers["Warning"] = '299 - "This endpoint is deprecated. Please use /api/v1/* endpoints."'
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2026-01-01T00:00:00Z"

    return response


# Include v1 router (versioned endpoints)
app.include_router(v1_router, prefix="/api/v1")

# Include legacy routers (deprecated but backward compatible)
app.include_router(health.router, prefix="/api", tags=["health (legacy)"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat (legacy)"])
app.include_router(vision.router, prefix="/api/vision", tags=["vision (legacy)"])
app.include_router(reasoning.router, prefix="/api/reasoning", tags=["reasoning (legacy)"])
app.include_router(computer.router, prefix="/api/computer", tags=["computer (legacy)"])
app.include_router(costs.router, prefix="/api/costs", tags=["costs (legacy)"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents (legacy)"])
app.include_router(vendors.router, prefix="/api/vendors", tags=["vendors (legacy)"])
app.include_router(commitments.router, prefix="/api/commitments", tags=["commitments (legacy)"])
app.include_router(interactions.router, prefix="/api/interactions", tags=["interactions (legacy)"])
# app.include_router(email.router, tags=["email"])  # Temporarily disabled due to OAuth config issue


@app.get("/")
async def root():
    """
    API root endpoint with version information.

    Returns API metadata and available versions.
    """
    return {
        "name": "Local Assistant API",
        "version": API_VERSION,
        "description": "Unicorn-grade AI assistant with vision, reasoning, and computer use",
        "api_versions": API_VERSIONS,
        "endpoints": {
            "v1": "/api/v1",
            "legacy": "/api (deprecated)",
            "docs": "/docs",
            "metrics": "/metrics",
        },
        "deprecation_notice": "Legacy /api/* endpoints are deprecated. Please migrate to /api/v1/*",
    }


@app.get("/metrics")
async def metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns all collected metrics in Prometheus text format:
    - General metrics (requests, latency, costs, errors)
    - Life Graph metrics (documents, vendors, commitments)
    """
    # Collect metrics from both collectors
    general_metrics = get_metrics_collector()
    lifegraph_metrics = get_lifegraph_metrics()

    # Combine metrics (both use same default registry)
    metrics_data = general_metrics.export_metrics()

    return Response(
        content=metrics_data,
        media_type=general_metrics.get_content_type(),
    )


# Register RFC 7807 exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
