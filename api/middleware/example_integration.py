"""Example showing how to integrate rate limiting into main.py.

This file demonstrates the minimal changes needed to enable rate limiting.
Copy the relevant sections into your api/main.py file.
"""

# ============================================================================
# STEP 1: Add import at the top of main.py (after other imports)
# ============================================================================

from api.middleware.rate_limit import RateLimitMiddleware, get_redis_url


# ============================================================================
# STEP 2: Add middleware after CORS middleware in main.py
# ============================================================================

# Existing CORS middleware (already in main.py around line 68-80)
"""
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
"""

# NEW: Add rate limiting middleware right after CORS
"""
app.add_middleware(
    RateLimitMiddleware,
    redis_url=get_redis_url()
)
"""


# ============================================================================
# COMPLETE EXAMPLE: Full middleware section of main.py
# ============================================================================

COMPLETE_MIDDLEWARE_SECTION = """
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

# Rate limiting middleware (NEW)
app.add_middleware(
    RateLimitMiddleware,
    redis_url=get_redis_url()
)
"""


# ============================================================================
# OPTIONAL: Custom configuration path
# ============================================================================

CUSTOM_CONFIG_EXAMPLE = """
# If you want to use a custom config file location:
app.add_middleware(
    RateLimitMiddleware,
    redis_url=get_redis_url(),
    config_path="/path/to/custom/rate_limits.yaml"
)
"""


# ============================================================================
# TESTING: Verify rate limiting is working
# ============================================================================

TESTING_COMMANDS = """
# Start the application
uvicorn api.main:app --reload --port 8000

# In another terminal, test rate limiting:

# 1. Test default limits (100 req/min on /api/health)
for i in {1..120}; do
  curl -s -o /dev/null -w "%{http_code}\\n" http://localhost:8000/api/health
done
# Expected: 100x 200, then 20x 429

# 2. Test endpoint-specific limits (10 req/min on /api/vision)
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\\n" http://localhost:8000/api/vision
done
# Expected: 10x 200, then 5x 429

# 3. Check rate limit headers
curl -v http://localhost:8000/api/health 2>&1 | grep "X-RateLimit"
# Expected:
# X-RateLimit-Limit-Minute: 100
# X-RateLimit-Remaining-Minute: 99
# X-RateLimit-Limit-Hour: 1000
# X-RateLimit-Remaining-Hour: 999

# 4. Test with user ID
curl -H "X-User-ID: user123" -v http://localhost:8000/api/chat
# Rate limiting will be per-user instead of per-IP

# 5. Check Redis keys
redis-cli -p 6380 keys "ratelimit:*"
redis-cli -p 6380 get "ratelimit:ip:127.0.0.1:60:XXXX"
"""


# ============================================================================
# MONITORING: Integration with existing observability
# ============================================================================

MONITORING_INTEGRATION = """
# Future enhancement: Add Prometheus metrics for rate limiting

from prometheus_client import Counter, Histogram

rate_limit_hits = Counter(
    'rate_limit_hits_total',
    'Total number of rate limit hits',
    ['endpoint', 'limit_type']
)

rate_limit_latency = Histogram(
    'rate_limit_check_duration_seconds',
    'Time spent checking rate limits',
    ['endpoint']
)

# Use in middleware:
# rate_limit_hits.labels(endpoint=path, limit_type='per_minute').inc()
"""


if __name__ == "__main__":
    print("=" * 80)
    print("RATE LIMITING INTEGRATION GUIDE")
    print("=" * 80)
    print("\n1. Add this import to api/main.py:")
    print("   from api.middleware.rate_limit import RateLimitMiddleware, get_redis_url")
    print("\n2. Add this middleware after CORS middleware:")
    print(COMPLETE_MIDDLEWARE_SECTION)
    print("\n3. Test with these commands:")
    print(TESTING_COMMANDS)
    print("\n4. Adjust limits in config/rate_limits.yaml as needed")
    print("=" * 80)
