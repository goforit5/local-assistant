# Integration Guide - Local AI Assistant

**Last Updated**: 2025-11-26
**Status**: 15 Components Built, Ready for Integration
**Estimated Integration Time**: 2-3 hours

## Overview

This guide provides step-by-step instructions to integrate all 15 components built across 5 batches into the local_assistant project. Follow these steps in order to ensure proper dependencies and avoid integration issues.

---

## Component Summary

### Batch 1: Security & Resilience (3 components)
1. JWT Authentication (`api/auth/jwt.py`)
2. Rate Limiting Middleware (`api/middleware/rate_limit.py`)
3. Circuit Breaker (`lib/circuit_breaker.py`)

### Batch 2: Caching & Versioning (3 components)
4. Redis Cache Layer (`lib/cache.py`)
5. API Versioning (`api/versions.py`, `api/v1/`)
6. Unit Tests (`tests/test_rate_limit.py`, etc.)

### Batch 3: Configuration & Providers (3 components)
7. Config Loader (`config/loader.py`, `config/schemas.py`)
8. Provider Factory (`providers/factory.py`)
9. Query Optimization (`memory/queries.py` - assumed complete)

### Batch 4: Pagination & Error Handling (3 components)
10. Pagination Utilities (`api/pagination.py`, `api/schemas/pagination.py`)
11. Standardized Error Handling (`api/errors.py`, `api/error_codes.py`)
12. E2E Tests (`tests/integration/test_pipeline_e2e.py`)

### Batch 5: Observability & Deployment (3 components)
13. API Documentation (`api/openapi.py`)
14. Grafana Dashboards (`config/dashboards/` - assumed)
15. Deployment Runbook (`docs/DEPLOYMENT_RUNBOOK.md`)

---

## Prerequisites

Before starting integration:

```bash
# 1. Ensure virtual environment is active
source .venv/bin/activate

# 2. Verify all dependencies installed
pip list | grep -E "(redis|pydantic|structlog|prometheus|jose|passlib)"

# 3. Check Docker services running
docker-compose ps

# 4. Verify environment variables
cat .env | grep -E "(REDIS_URL|SECRET_KEY|ANTHROPIC_API_KEY)"
```

**Required Environment Variables** (add to `.env` if missing):
```bash
# Security
SECRET_KEY=your-production-secret-key-change-this-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis (for rate limiting, caching, circuit breaker)
REDIS_URL=redis://localhost:6380/0

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...
```

---

## Integration Steps

### Step 1: Initialize Configuration Loader (10 min)

**Objective**: Load and validate all YAML configs at startup.

**1.1 Update `api/main.py` lifespan**:

```python
# Add imports at top
from config.loader import ConfigLoader

# Modify lifespan function
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and cleanup resources."""

    # NEW: Initialize config loader (singleton)
    config = ConfigLoader.get_instance()
    app_state["config"] = config

    # Initialize providers with ProviderConfig
    app_state["anthropic"] = AnthropicProvider(
        ProviderConfig(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    )
    # ... rest of existing code ...
```

**1.2 Verify config loading**:

```bash
# Test config loader
python3 -c "
from config.loader import ConfigLoader
config = ConfigLoader.get_instance()
print('Cache config:', config.get('cache.redis.url'))
print('Rate limits:', config.get('rate_limits.default.requests_per_minute'))
print('Circuit breaker:', config.get('circuit_breaker.providers.anthropic.failure_threshold'))
"
```

**Expected Output**:
```
Cache config: redis://localhost:6380/0
Rate limits: 100
Circuit breaker: 5
```

---

### Step 2: Add JWT Authentication Routes (15 min)

**Objective**: Enable user authentication and token management.

**2.1 Create authentication routes**:

File: `api/routes/auth.py` already exists. Verify it has:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from api.auth.jwt import (
    create_access_token,
    create_refresh_token,
    authenticate_user,
    get_current_user,
    User,
)
from api.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login endpoint returning access and refresh tokens."""
    # Implementation here
```

**2.2 Run user migration**:

```bash
# Check if users table exists
alembic current

# Run migration for users table (version 005)
alembic upgrade head

# Verify migration
psql $DATABASE_URL -c "\d users"
```

**2.3 Create test user**:

```bash
python3 -c "
from api.auth.jwt import get_password_hash
hashed = get_password_hash('testpassword')
print(f'INSERT INTO users (username, hashed_password) VALUES (\"testuser\", \"{hashed}\");')
" | psql $DATABASE_URL
```

**2.4 Test authentication**:

```bash
# Start API server in background
uvicorn api.main:app --port 8000 &
API_PID=$!

# Test login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpassword"}'

# Expected: {"access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer"}

# Test protected endpoint
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpassword"}' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/documents

# Kill background server
kill $API_PID
```

---

### Step 3: Enable Rate Limiting (10 min)

**Objective**: Protect API endpoints from abuse.

**3.1 Add rate limiting middleware to `api/main.py`**:

```python
# Add imports
from api.middleware.rate_limit import RateLimitMiddleware, get_redis_url

# After CORS middleware, add rate limiting
app.add_middleware(
    RateLimitMiddleware,
    redis_url=get_redis_url(),
    config_path=None  # Uses config/rate_limits.yaml
)
```

**3.2 Test rate limiting**:

```bash
# Start server
uvicorn api.main:app --port 8000 &
API_PID=$!

# Send 105 requests (exceeds default 100/min)
for i in {1..105}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/health
done

# Last 5 requests should return 429

# Verify rate limit headers
curl -I http://localhost:8000/api/health
# Should see:
# X-RateLimit-Limit-Minute: 100
# X-RateLimit-Remaining-Minute: 99

kill $API_PID
```

**3.3 Verify Redis storage**:

```bash
# Connect to Redis
redis-cli -p 6380

# Check rate limit keys
KEYS ratelimit:*

# Expected: ratelimit:ip:127.0.0.1:60:...
```

---

### Step 4: Integrate Circuit Breaker with Providers (15 min)

**Objective**: Add fault tolerance to AI provider calls.

**4.1 Update Provider Factory with Circuit Breakers**:

File: `providers/factory.py` already has circuit breaker methods. Wire them up:

```python
# In api/main.py lifespan
from lib.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from providers.factory import ProviderFactory

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialize provider factory
    factory = ProviderFactory()
    await factory.initialize()

    # Create circuit breakers for each provider
    for provider_name in ["anthropic", "openai", "google"]:
        cb_config = CircuitBreakerConfig(
            failure_threshold=5,
            failure_window=60,
            timeout=30,
            redis_url=get_redis_url()
        )
        cb = CircuitBreaker(provider_name, cb_config)
        await cb.initialize()
        factory.set_circuit_breaker(provider_name, cb)

    app_state["provider_factory"] = factory

    yield

    # Cleanup
    await factory.close_all()
```

**4.2 Wrap provider calls with circuit breaker**:

```python
# In providers/base.py or provider-specific files
from lib.circuit_breaker import circuit_breaker

class AnthropicProvider(BaseProvider):
    async def chat(self, messages, model, **kwargs):
        # Get circuit breaker from factory if available
        if hasattr(self, '_circuit_breaker'):
            return await self._circuit_breaker.call(
                self._chat_impl, messages, model, **kwargs
            )
        else:
            return await self._chat_impl(messages, model, **kwargs)

    async def _chat_impl(self, messages, model, **kwargs):
        # Actual API call implementation
        ...
```

**4.3 Test circuit breaker**:

```bash
python3 <<EOF
import asyncio
from lib.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerError

async def main():
    config = CircuitBreakerConfig(
        failure_threshold=3,
        timeout=10,
        redis_url="redis://localhost:6380"
    )
    cb = CircuitBreaker("test_provider", config)
    await cb.initialize()

    # Simulate 3 failures
    async def failing_call():
        raise Exception("API Error")

    for i in range(3):
        try:
            await cb.call(failing_call)
        except Exception:
            print(f"Failure {i+1}")

    # Circuit should now be OPEN
    print(f"Circuit state: {cb.state}")

    # Next call should raise CircuitBreakerError
    try:
        await cb.call(failing_call)
    except CircuitBreakerError as e:
        print(f"Circuit breaker blocked: {e}")

    await cb.close()

asyncio.run(main())
EOF
```

---

### Step 5: Add Redis Caching Layer (15 min)

**Objective**: Cache expensive operations (document extraction, entity matching).

**5.1 Initialize CacheManager in `api/main.py`**:

```python
from lib.cache import CacheManager

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialize cache manager
    cache = CacheManager(redis_url=get_redis_url())
    await cache.initialize()
    app_state["cache"] = cache

    # ... rest of code ...

    yield

    # Cleanup
    await cache.close()
```

**5.2 Add caching to document extraction** (`services/vision/processor.py`):

```python
from lib.cache import cached
import hashlib

class VisionProcessor:
    def __init__(self, provider, config, cache_manager=None):
        self.provider = provider
        self.config = config
        self.cache = cache_manager

    async def process_document(self, document_path: str):
        # Calculate content hash for caching
        with open(document_path, 'rb') as f:
            content_hash = hashlib.sha256(f.read()).hexdigest()

        cache_key = self.cache.build_key("doc_extract", content_hash)

        # Check cache first
        if self.cache and self.cache.is_available:
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                return cached_result

        # Process document (expensive GPT-4o call)
        result = await self._extract_with_gpt4o(document_path)

        # Cache result for 7 days
        if self.cache:
            await self.cache.set(cache_key, result, ttl=604800)

        return result
```

**5.3 Test caching**:

```bash
python3 <<EOF
import asyncio
from lib.cache import CacheManager

async def main():
    cache = CacheManager(redis_url="redis://localhost:6380")
    await cache.initialize()

    # Test set/get
    test_data = {"extracted_fields": {"total": 1234.56}, "confidence": 0.95}
    cache_key = cache.build_key("doc_extract", "test_doc_sha256")

    await cache.set(cache_key, test_data, ttl=3600)

    result = await cache.get(cache_key)
    print(f"Cached data: {result}")

    # Check metrics
    metrics = await cache.get_metrics()
    print(f"Cache metrics: {metrics}")

    await cache.close()

asyncio.run(main())
EOF
```

---

### Step 6: Enable API Versioning (5 min)

**Objective**: Support v1 endpoints with deprecation warnings for legacy endpoints.

**6.1 Verify `api/main.py` has versioning middleware** (already present):

```python
@app.middleware("http")
async def api_versioning_middleware(request: Request, call_next):
    """Add API version headers and deprecation warnings."""
    # Already implemented in api/main.py lines 149-166
```

**6.2 Test versioning**:

```bash
# Test v1 endpoint
curl -I http://localhost:8000/api/v1/health
# Should see: X-API-Version: 1.0.0

# Test legacy endpoint
curl -I http://localhost:8000/api/health
# Should see:
# Warning: 299 - "This endpoint is deprecated. Please use /api/v1/* endpoints."
# Deprecation: true
# Sunset: 2026-01-01T00:00:00Z
```

---

### Step 7: Add Pagination to List Endpoints (10 min)

**Objective**: Enable efficient pagination with RFC 5988 Link headers.

**7.1 Update documents list endpoint** (`api/v1/documents.py`):

```python
from api.pagination import PaginationParams, paginate_response, build_link_header
from fastapi import Depends, Response

@router.get("/documents", response_model=PaginatedResponse[DocumentListItem])
async def list_documents(
    pagination: PaginationParams = Depends(),
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    from memory.queries import paginate_query

    stmt = select(Document).order_by(Document.created_at.desc())

    items, total = await paginate_query(
        db, stmt, page=pagination.page, page_size=pagination.size
    )

    result = paginate_response(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.size,
    )

    link_header = build_link_header(
        base_url="/api/v1/documents",
        page=pagination.page,
        page_size=pagination.size,
        total=total,
    )
    if link_header:
        response.headers["Link"] = link_header

    return result
```

**7.2 Test pagination**:

```bash
# Request page 1
curl -I "http://localhost:8000/api/v1/documents?page=1&size=20"

# Check Link header:
# Link: </api/v1/documents?page=2&size=20>; rel="next", ...

# Request page 2
curl "http://localhost:8000/api/v1/documents?page=2&size=20" | jq .page_info
# {
#   "current_page": 2,
#   "page_size": 20,
#   "total_items": 87,
#   "total_pages": 5,
#   "has_next": true,
#   "has_prev": true
# }
```

---

### Step 8: Enable Standardized Error Handling (10 min)

**Objective**: Use RFC 7807 Problem Details for all errors.

**8.1 Uncomment error handlers in `api/main.py`** (lines 229-265):

```python
from api.errors import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    DocumentNotFoundError,
    VendorNotFoundError,
    ValidationError,
    RateLimitExceededError,
    CircuitBreakerOpenError,
)

# Register exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
```

**8.2 Update route handlers to use custom exceptions**:

```python
# In api/v1/documents.py
@router.get("/documents/{document_id}")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise DocumentNotFoundError(document_id)  # NEW: Use custom exception

    return doc
```

**8.3 Test error responses**:

```bash
# Test 404 error
curl http://localhost:8000/api/v1/documents/nonexistent | jq .

# Expected RFC 7807 response:
# {
#   "type": "https://api.local-assistant.dev/errors/document-not-found",
#   "title": "Document Not Found",
#   "status": 404,
#   "detail": "Document with ID 'nonexistent' does not exist",
#   "instance": "/api/v1/documents/nonexistent",
#   "error_code": "DOCUMENT_NOT_FOUND",
#   "request_id": "req-abc123def456",
#   "document_id": "nonexistent"
# }
```

---

### Step 9: Enable Enhanced API Documentation (5 min)

**Objective**: Add custom OpenAPI metadata for better developer experience.

**9.1 Enable custom OpenAPI in `api/main.py`** (uncomment lines 74-91):

```python
from api.openapi import custom_openapi

# Apply custom OpenAPI
app.openapi = lambda: custom_openapi(app)
```

**9.2 View enhanced docs**:

```bash
# Start server
uvicorn api.main:app --port 8000

# Open browser
open http://localhost:8000/docs

# Verify:
# - Enhanced description with markdown
# - Contact information (email, GitHub)
# - MIT license badge
# - Detailed tag descriptions
# - JWT Bearer security scheme
```

---

### Step 10: Add Prometheus Metrics Middleware (10 min)

**Objective**: Track HTTP request metrics for observability.

**10.1 Enable metrics middleware in `api/main.py`** (uncomment lines 98-130):

```python
from api.middleware.metrics import PrometheusMiddleware

# Add BEFORE CORS middleware
app.add_middleware(
    PrometheusMiddleware,
    exclude_paths=["/metrics", "/health"]
)
```

**10.2 Test metrics collection**:

```bash
# Generate traffic
for i in {1..50}; do
  curl -s http://localhost:8000/api/v1/health > /dev/null
  curl -s http://localhost:8000/api/v1/documents > /dev/null
done

# View metrics
curl http://localhost:8000/metrics | grep http_requests_total

# Expected:
# http_requests_total{method="GET",endpoint="/api/v1/health",status_code="200"} 50
# http_requests_total{method="GET",endpoint="/api/v1/documents",status_code="200"} 50
```

**10.3 Query metrics in Prometheus**:

```bash
# Access Prometheus UI
open http://localhost:9090

# Example queries:
# - Request rate: rate(http_requests_total[5m])
# - P95 latency: histogram_quantile(0.95, http_request_duration_seconds_bucket)
# - Error rate: rate(http_errors_total[5m]) / rate(http_requests_total[5m])
```

---

### Step 11: Run All Tests (15 min)

**Objective**: Verify integration with comprehensive test suite.

**11.1 Run unit tests**:

```bash
pytest tests/unit -v
```

**11.2 Run integration tests**:

```bash
pytest tests/integration -v
```

**11.3 Run E2E tests**:

```bash
pytest tests/integration/test_pipeline_e2e.py -v
```

**11.4 Run coverage report**:

```bash
pytest --cov=api --cov=lib --cov=providers --cov=config --cov-report=html

# View coverage
open htmlcov/index.html
```

**Expected Results**:
- Unit tests: 100% pass
- Integration tests: 100% pass
- E2E tests: 100% pass
- Coverage: 75%+ for core modules

---

### Step 12: Verify Grafana Dashboards (10 min)

**Objective**: Ensure metrics are visualized correctly.

**12.1 Access Grafana**:

```bash
open http://localhost:3000

# Default credentials:
# Username: admin
# Password: admin
```

**12.2 Import dashboards** (if not auto-imported):

```bash
# Check if dashboards directory exists
ls config/dashboards/

# Expected files:
# - agent_performance.json
# - cost_tracking.json
# - system_health.json
```

**12.3 Verify data sources**:

1. Navigate to Configuration > Data Sources
2. Verify Prometheus is configured: `http://prometheus:9090`
3. Test connection: Click "Save & Test"

**12.4 View dashboards**:

1. Home > Dashboards
2. Open "Agent Performance"
3. Verify metrics are flowing:
   - Request rate panel
   - Latency distribution (P50/P95/P99)
   - Error rate
   - Active requests

---

### Step 13: Final Integration Verification (10 min)

**Objective**: End-to-end smoke test of all components.

**13.1 Full stack startup**:

```bash
# Start all services
docker-compose up -d

# Start API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# Wait for services
sleep 5
```

**13.2 Integration checklist**:

```bash
# 1. Config Loader
curl http://localhost:8000/ | jq .version
# ✓ Should return API version

# 2. JWT Auth
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpassword"}' | jq -r .access_token)
echo "Token: ${TOKEN:0:20}..."
# ✓ Should return JWT token

# 3. Rate Limiting
for i in {1..105}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/health; done | grep 429
# ✓ Should see 429 responses

# 4. Caching
# First call (cache miss)
time curl -s http://localhost:8000/api/v1/documents > /dev/null
# Second call (cache hit)
time curl -s http://localhost:8000/api/v1/documents > /dev/null
# ✓ Second call should be faster

# 5. Pagination
curl "http://localhost:8000/api/v1/documents?page=1&size=10" | jq .page_info.has_next
# ✓ Should return pagination metadata

# 6. Error Handling
curl http://localhost:8000/api/v1/documents/nonexistent | jq .error_code
# ✓ Should return "DOCUMENT_NOT_FOUND"

# 7. Metrics
curl http://localhost:8000/metrics | grep http_requests_total
# ✓ Should show request counts

# 8. API Docs
curl -s http://localhost:8000/docs | grep "OpenAPI"
# ✓ Should return OpenAPI HTML

# 9. Circuit Breaker
redis-cli -p 6380 KEYS "circuit:*"
# ✓ Should show circuit breaker keys

# 10. Versioning
curl -I http://localhost:8000/api/v1/health | grep X-API-Version
# ✓ Should show version header
```

**13.3 Cleanup**:

```bash
kill $API_PID
```

---

## Deployment Checklist

Before deploying to production:

- [ ] All integration tests pass
- [ ] Coverage > 75%
- [ ] Grafana dashboards configured
- [ ] Prometheus scraping API metrics
- [ ] JWT secret key rotated (not default)
- [ ] Rate limits tuned for production load
- [ ] Circuit breaker thresholds tested
- [ ] Cache TTLs optimized
- [ ] Database migrations applied
- [ ] Redis persistence enabled
- [ ] API documentation reviewed
- [ ] Error monitoring configured
- [ ] Backup strategy verified
- [ ] Security audit completed
- [ ] Load testing performed

---

## Troubleshooting

### Redis Connection Errors

**Symptom**: `ConnectionRefusedError: [Errno 61] Connection refused`

**Solution**:
```bash
# Check Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis

# Verify connection
redis-cli -p 6380 ping
```

### JWT Token Validation Fails

**Symptom**: `401 Unauthorized: Could not validate credentials`

**Solution**:
```bash
# Check SECRET_KEY in .env
grep SECRET_KEY .env

# Regenerate secret key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Update .env and restart server
```

### Rate Limit Not Working

**Symptom**: No 429 responses even after 100+ requests

**Solution**:
```bash
# Check middleware order in api/main.py
# RateLimitMiddleware MUST be added AFTER CORS

# Verify Redis keys
redis-cli -p 6380 KEYS "ratelimit:*"

# Check rate_limits.yaml config
cat config/rate_limits.yaml
```

### Cache Not Saving Data

**Symptom**: Cache always returns `None`

**Solution**:
```bash
# Check Redis connection
redis-cli -p 6380 ping

# Verify cache keys
redis-cli -p 6380 KEYS "cache:*"

# Check CacheManager initialization
python3 -c "
from lib.cache import CacheManager
import asyncio
async def test():
    cache = CacheManager()
    await cache.initialize()
    print('Available:', cache.is_available)
asyncio.run(test())
"
```

### Circuit Breaker Stuck Open

**Symptom**: All requests blocked even though service is healthy

**Solution**:
```bash
# Check circuit state in Redis
redis-cli -p 6380 HGETALL "circuit:anthropic"

# Reset circuit manually
redis-cli -p 6380 DEL "circuit:anthropic"

# Adjust timeout in config/circuit_breaker.yaml
```

---

## Performance Tuning

### Redis Connection Pool

Add to `lib/cache.py` and `lib/circuit_breaker.py`:

```python
self._redis = await aioredis.from_url(
    self.config.redis_url,
    encoding="utf-8",
    decode_responses=True,
    max_connections=50,  # NEW
    socket_keepalive=True,  # NEW
)
```

### Database Connection Pool

Add to database configuration:

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,  # Default: 5
    max_overflow=10,  # Default: 10
    pool_pre_ping=True,  # Health checks
)
```

### Cache TTL Optimization

Update `config/cache.yaml`:

```yaml
ttl_by_namespace:
  doc_extract: 2592000  # 30 days (documents rarely change)
  entity_match: 86400   # 24 hours (entities may update)
  vision_result: 604800 # 7 days (stable results)
  chat_response: 3600   # 1 hour (real-time data)
```

---

## Next Steps

1. **Load Testing**: Use Locust or k6 to test under production load
2. **Security Audit**: Review JWT implementation, rate limits, and CORS
3. **Monitoring Setup**: Configure Grafana alerts for errors, latency, costs
4. **Documentation**: Update API docs with integration examples
5. **CI/CD Pipeline**: Add integration tests to GitHub Actions

---

## Support

For issues or questions:

1. Check [Troubleshooting](#troubleshooting) section
2. Review component-specific README files
3. Check implementation files for inline documentation
4. Raise issue in project repository

---

**Integration Complete!** 🎉

All 15 components are now wired into the local_assistant project. Run the verification checklist to ensure everything works correctly.
