"""
Prometheus Metrics Middleware for FastAPI

Tracks HTTP request metrics including:
- Request counter (by endpoint, method, status)
- Request latency histogram (P50, P95, P99)
- Active requests gauge
- Request/response size histograms
- Error counter (by error type)
"""

from __future__ import annotations

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from prometheus_client import Counter, Histogram, Gauge
import structlog

logger = structlog.get_logger(__name__)


# HTTP Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=["method", "endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    labelnames=["method", "endpoint"],
)

http_request_size_bytes = Histogram(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    labelnames=["method", "endpoint"],
    buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
)

http_response_size_bytes = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    labelnames=["method", "endpoint", "status_code"],
    buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
)

http_errors_total = Counter(
    "http_errors_total",
    "Total number of HTTP errors",
    labelnames=["method", "endpoint", "error_type", "status_code"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect Prometheus metrics for all HTTP requests.

    Metrics collected:
    - http_requests_total: Counter for total requests
    - http_request_duration_seconds: Histogram for request latency
    - http_requests_in_progress: Gauge for active requests
    - http_request_size_bytes: Histogram for request payload size
    - http_response_size_bytes: Histogram for response payload size
    - http_errors_total: Counter for errors by type

    Usage:
        app.add_middleware(PrometheusMiddleware)
    """

    def __init__(self, app: ASGIApp, exclude_paths: list[str] | None = None):
        """
        Initialize metrics middleware.

        Args:
            app: ASGI application
            exclude_paths: List of paths to exclude from metrics (e.g., ["/metrics", "/health"])
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/metrics"]
        logger.info(
            "prometheus_middleware_initialized",
            exclude_paths=self.exclude_paths
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and collect metrics.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from handler
        """
        # Skip metrics collection for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Normalize endpoint path (remove IDs, query params)
        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method

        # Track request size
        request_size = int(request.headers.get("content-length", 0))
        http_request_size_bytes.labels(
            method=method,
            endpoint=endpoint,
        ).observe(request_size)

        # Increment active requests
        http_requests_in_progress.labels(
            method=method,
            endpoint=endpoint,
        ).inc()

        # Track request timing
        start_time = time.time()
        status_code = 500
        error_type = None

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

            # Track response size
            response_size = int(response.headers.get("content-length", 0))
            http_response_size_bytes.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).observe(response_size)

            # Determine error type for 4xx/5xx responses
            if status_code >= 400:
                error_type = self._get_error_type(status_code)
                http_errors_total.labels(
                    method=method,
                    endpoint=endpoint,
                    error_type=error_type,
                    status_code=str(status_code),
                ).inc()

            return response

        except Exception as exc:
            # Track unhandled exceptions
            error_type = type(exc).__name__
            http_errors_total.labels(
                method=method,
                endpoint=endpoint,
                error_type=error_type,
                status_code=str(status_code),
            ).inc()

            logger.error(
                "request_exception",
                method=method,
                endpoint=endpoint,
                error=str(exc),
                error_type=error_type,
            )
            raise

        finally:
            # Calculate request duration
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            # Decrement active requests
            http_requests_in_progress.labels(
                method=method,
                endpoint=endpoint,
            ).dec()

            logger.debug(
                "request_completed",
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration_ms=f"{duration * 1000:.2f}",
                error_type=error_type,
            )

    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize endpoint path to reduce cardinality.

        Replaces UUIDs, IDs, and other variable parts with placeholders.

        Examples:
            /api/v1/documents/123 -> /api/v1/documents/{id}
            /api/v1/vendors/abc-def-ghi -> /api/v1/vendors/{id}
            /api/chat -> /api/chat

        Args:
            path: Request path

        Returns:
            Normalized path
        """
        parts = path.split("/")
        normalized = []

        for i, part in enumerate(parts):
            # Replace UUIDs and IDs with placeholder
            if part and (
                self._is_uuid(part)
                or self._is_numeric_id(part)
                or (i > 0 and parts[i - 1] in ["documents", "vendors", "commitments", "interactions"])
            ):
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)

    @staticmethod
    def _is_uuid(value: str) -> bool:
        """Check if string is a UUID"""
        return (
            len(value) == 36
            and value.count("-") == 4
            and all(c in "0123456789abcdef-" for c in value.lower())
        )

    @staticmethod
    def _is_numeric_id(value: str) -> bool:
        """Check if string is a numeric ID"""
        return value.isdigit() and len(value) <= 20

    @staticmethod
    def _get_error_type(status_code: int) -> str:
        """
        Map HTTP status code to error type.

        Args:
            status_code: HTTP status code

        Returns:
            Error type string
        """
        if status_code == 400:
            return "bad_request"
        elif status_code == 401:
            return "unauthorized"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "not_found"
        elif status_code == 422:
            return "validation_error"
        elif status_code == 429:
            return "rate_limit"
        elif status_code >= 500:
            return "internal_error"
        else:
            return f"http_{status_code}"


def get_metrics_summary() -> dict:
    """
    Get summary of current HTTP metrics.

    Returns:
        Dictionary with metrics summary
    """
    return {
        "description": "HTTP request metrics for FastAPI application",
        "metrics": {
            "http_requests_total": "Total number of HTTP requests by method, endpoint, and status",
            "http_request_duration_seconds": "Request latency distribution (P50, P95, P99)",
            "http_requests_in_progress": "Number of currently active requests",
            "http_request_size_bytes": "Request payload size distribution",
            "http_response_size_bytes": "Response payload size distribution",
            "http_errors_total": "Total errors by method, endpoint, error type, and status",
        },
        "labels": {
            "method": "HTTP method (GET, POST, PUT, DELETE, etc.)",
            "endpoint": "Normalized endpoint path (IDs replaced with {id})",
            "status_code": "HTTP status code",
            "error_type": "Error classification (bad_request, not_found, etc.)",
        },
    }
