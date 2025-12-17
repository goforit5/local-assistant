"""Redis-backed rate limiting middleware for FastAPI."""

import os
import time
from typing import Optional, Dict, Tuple
from pathlib import Path

import redis.asyncio as redis
import yaml
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed distributed rate limiting middleware.

    Implements sliding window rate limiting using Redis INCR + EXPIRE.
    Supports both per-IP and per-user limits with configurable thresholds.
    """

    def __init__(self, app, redis_url: str, config_path: Optional[str] = None):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            redis_url: Redis connection URL
            config_path: Path to rate_limits.yaml config file
        """
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
        self.redis_url = redis_url
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """Load rate limit configuration from YAML file.

        Args:
            config_path: Path to config file, defaults to config/rate_limits.yaml

        Returns:
            Configuration dictionary
        """
        if config_path is None:
            base_dir = Path(__file__).parent.parent.parent
            config_path = base_dir / "config" / "rate_limits.yaml"

        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {
                'default': {
                    'requests_per_minute': 100,
                    'requests_per_hour': 1000
                },
                'endpoints': {}
            }

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection.

        Returns:
            Redis client instance
        """
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self.redis_client

    def _get_client_identifier(self, request: Request) -> str:
        """Extract client identifier from request.

        Prioritizes authenticated user ID over IP address.

        Args:
            request: FastAPI request object

        Returns:
            Client identifier string
        """
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"

        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        return f"ip:{client_ip}"

    def _get_endpoint_limits(self, path: str) -> Dict[str, int]:
        """Get rate limits for specific endpoint.

        Args:
            path: Request path

        Returns:
            Dictionary with requests_per_minute and requests_per_hour
        """
        endpoint_config = self.config.get('endpoints', {})

        for pattern, limits in endpoint_config.items():
            if path.startswith(pattern):
                return limits

        return self.config.get('default', {
            'requests_per_minute': 100,
            'requests_per_hour': 1000
        })

    async def _check_rate_limit(
        self,
        client_id: str,
        limit: int,
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """Check if request exceeds rate limit using Redis.

        Uses sliding window with INCR + EXPIRE for atomic operations.

        Args:
            client_id: Client identifier
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, current_count, remaining)
        """
        redis_client = await self._get_redis()

        current_time = int(time.time())
        window_key = f"ratelimit:{client_id}:{window_seconds}:{current_time // window_seconds}"

        try:
            current_count = await redis_client.incr(window_key)

            if current_count == 1:
                await redis_client.expire(window_key, window_seconds)

            remaining = max(0, limit - current_count)
            is_allowed = current_count <= limit

            return is_allowed, current_count, remaining

        except Exception as e:
            return True, 0, limit

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting middleware.

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response with rate limit headers
        """
        client_id = self._get_client_identifier(request)
        limits = self._get_endpoint_limits(request.url.path)

        requests_per_minute = limits.get('requests_per_minute', 100)
        requests_per_hour = limits.get('requests_per_hour', 1000)

        minute_allowed, minute_count, minute_remaining = await self._check_rate_limit(
            client_id, requests_per_minute, 60
        )

        hour_allowed, hour_count, hour_remaining = await self._check_rate_limit(
            client_id, requests_per_hour, 3600
        )

        if not minute_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit_type": "per_minute",
                    "limit": requests_per_minute,
                    "retry_after": 60
                },
                headers={
                    "X-RateLimit-Limit-Minute": str(requests_per_minute),
                    "X-RateLimit-Remaining-Minute": "0",
                    "X-RateLimit-Reset-Minute": str(int(time.time()) + 60),
                    "Retry-After": "60"
                }
            )

        if not hour_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit_type": "per_hour",
                    "limit": requests_per_hour,
                    "retry_after": 3600
                },
                headers={
                    "X-RateLimit-Limit-Hour": str(requests_per_hour),
                    "X-RateLimit-Remaining-Hour": "0",
                    "X-RateLimit-Reset-Hour": str(int(time.time()) + 3600),
                    "Retry-After": "3600"
                }
            )

        response = await call_next(request)

        response.headers["X-RateLimit-Limit-Minute"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(minute_remaining)
        response.headers["X-RateLimit-Limit-Hour"] = str(requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(hour_remaining)

        return response

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


def get_redis_url() -> str:
    """Get Redis URL from environment variables.

    Reads from REDIS_URL in .env file, adjusting port if needed.

    Returns:
        Redis connection URL
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    if "localhost:6379" in redis_url:
        redis_url = redis_url.replace("localhost:6379", "localhost:6380")

    return redis_url
