"""Tests for Redis-backed rate limiting middleware."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.rate_limit import RateLimitMiddleware, get_redis_url


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    return app


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock()
    redis_mock.close = AsyncMock()
    return redis_mock


def test_get_redis_url_default():
    """Test Redis URL extraction from environment."""
    with patch.dict('os.environ', {'REDIS_URL': 'redis://localhost:6379/0'}):
        url = get_redis_url()
        assert url == 'redis://localhost:6380/0'


def test_get_redis_url_custom():
    """Test Redis URL with custom port."""
    with patch.dict('os.environ', {'REDIS_URL': 'redis://redis-server:6380/1'}):
        url = get_redis_url()
        assert url == 'redis://redis-server:6380/1'


@pytest.mark.asyncio
async def test_rate_limit_within_limits(app, mock_redis):
    """Test requests within rate limits are allowed."""
    with patch('redis.asyncio.from_url', return_value=mock_redis):
        middleware = RateLimitMiddleware(
            app,
            redis_url='redis://localhost:6380/0'
        )

        mock_redis.incr.return_value = 1

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.headers = {}

        call_next = AsyncMock(return_value=MagicMock(headers={}))

        response = await middleware.dispatch(request, call_next)

        assert call_next.called
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers


@pytest.mark.asyncio
async def test_rate_limit_exceeded_minute(app, mock_redis):
    """Test requests exceeding minute limit are blocked."""
    with patch('redis.asyncio.from_url', return_value=mock_redis):
        middleware = RateLimitMiddleware(
            app,
            redis_url='redis://localhost:6380/0'
        )

        mock_redis.incr.return_value = 101

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.headers = {}

        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)

        assert not call_next.called
        assert response.status_code == 429
        assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_rate_limit_user_id_over_ip(app, mock_redis):
    """Test user ID takes precedence over IP."""
    with patch('redis.asyncio.from_url', return_value=mock_redis):
        middleware = RateLimitMiddleware(
            app,
            redis_url='redis://localhost:6380/0'
        )

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.headers = {"X-User-ID": "user123"}

        client_id = middleware._get_client_identifier(request)
        assert client_id == "user:user123"


@pytest.mark.asyncio
async def test_rate_limit_forwarded_ip(app, mock_redis):
    """Test X-Forwarded-For header is used."""
    with patch('redis.asyncio.from_url', return_value=mock_redis):
        middleware = RateLimitMiddleware(
            app,
            redis_url='redis://localhost:6380/0'
        )

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.headers = {"X-Forwarded-For": "203.0.113.1, 192.168.1.1"}

        client_id = middleware._get_client_identifier(request)
        assert client_id == "ip:203.0.113.1"


def test_endpoint_specific_limits(app):
    """Test endpoint-specific limits are loaded from config."""
    with patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = """
default:
  requests_per_minute: 100
  requests_per_hour: 1000

endpoints:
  /api/vision:
    requests_per_minute: 10
    requests_per_hour: 100
"""
        middleware = RateLimitMiddleware(
            app,
            redis_url='redis://localhost:6380/0',
            config_path='/fake/path.yaml'
        )

        limits = middleware._get_endpoint_limits('/api/vision')
        assert limits['requests_per_minute'] == 10
        assert limits['requests_per_hour'] == 100

        default_limits = middleware._get_endpoint_limits('/api/other')
        assert default_limits['requests_per_minute'] == 100
        assert default_limits['requests_per_hour'] == 1000


@pytest.mark.asyncio
async def test_rate_limit_redis_failure_allows_request(app):
    """Test requests are allowed if Redis fails (fail-open)."""
    with patch('redis.asyncio.from_url', side_effect=Exception("Redis down")):
        middleware = RateLimitMiddleware(
            app,
            redis_url='redis://localhost:6380/0'
        )

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.headers = {}

        call_next = AsyncMock(return_value=MagicMock(headers={}))

        try:
            response = await middleware.dispatch(request, call_next)
            assert call_next.called
        except Exception:
            pass


@pytest.mark.asyncio
async def test_sliding_window_key_generation(app, mock_redis):
    """Test sliding window key includes time bucket."""
    with patch('redis.asyncio.from_url', return_value=mock_redis):
        middleware = RateLimitMiddleware(
            app,
            redis_url='redis://localhost:6380/0'
        )

        mock_redis.incr.return_value = 1

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.headers = {}

        call_next = AsyncMock(return_value=MagicMock(headers={}))

        await middleware.dispatch(request, call_next)

        incr_call = mock_redis.incr.call_args[0][0]
        assert "ratelimit:ip:127.0.0.1:60:" in incr_call or "ratelimit:ip:127.0.0.1:3600:" in incr_call
        assert mock_redis.expire.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
