# ConfigLoader Usage Guide

## Quick Start

```python
from config import config

# Simple dot notation access
ttl = config.get("cache.ttl_by_namespace.doc_extract")
redis_url = config.get("cache.redis.url")
```

## Installation

The ConfigLoader is automatically initialized on first import. All YAML files in `/config` are loaded and validated at startup.

## Core Features

### 1. Dot Notation Access

Access nested configuration values using dot-separated paths:

```python
from config import config

# Cache configuration
doc_extract_ttl = config.get("cache.ttl_by_namespace.doc_extract")
# Returns: 604800 (7 days in seconds)

redis_url = config.get("cache.redis.url")
# Returns: "redis://localhost:6380"

max_object_size = config.get("cache.performance.max_object_size")
# Returns: 10485760 (10 MB)

# Rate limits
vision_rpm = config.get("rate_limits.endpoints./api/vision.requests_per_minute")
# Returns: 10

default_rpm = config.get("rate_limits.default.requests_per_minute")
# Returns: 100

# Circuit breaker
failure_threshold = config.get("circuit_breaker.defaults.failure_threshold")
# Returns: 5

google_timeout = config.get("circuit_breaker.providers.google.timeout")
# Returns: 45

# Model registry
claude_context = config.get("models_registry.vision_models.claude-sonnet-4-5.context_window")
# Returns: 200000

gpt4o_cost = config.get("models_registry.vision_models.gpt-4o.cost.input_per_1m")
# Returns: 2.50
```

### 2. Typed Configuration Objects

Get fully validated Pydantic models for type safety:

```python
from config import config

# Cache configuration
cache_config = config.get_cache_config()  # Returns CacheConfig instance
print(cache_config.default_ttl)  # 3600
print(cache_config.redis.url)    # "redis://localhost:6380"
print(cache_config.metrics.enabled)  # True

# Rate limiting
rate_limits = config.get_rate_limit_config()  # Returns RateLimitConfig instance
print(rate_limits.default.requests_per_minute)  # 100
print(rate_limits.endpoints["/api/vision"].requests_per_hour)  # 100

# Circuit breaker
circuit_breaker = config.get_circuit_breaker_config()  # Returns CircuitBreakerConfig
print(circuit_breaker.defaults.failure_threshold)  # 5
print(circuit_breaker.providers["google"].timeout)  # 45

# Model registry
models = config.get_model_registry_config()  # Returns ModelRegistryConfig
claude = models.vision_models["claude-sonnet-4-5"]
print(claude.context_window)  # 200000
print(claude.cost.input_per_1m)  # 3.0
```

### 3. Default Values

Provide fallback values for missing keys:

```python
from config import config

# Existing key - returns actual value
ttl = config.get("cache.default_ttl", default=999)
# Returns: 3600 (actual value from config)

# Missing key - returns default
custom_setting = config.get("custom.nonexistent.key", default="fallback")
# Returns: "fallback"

# No default specified - returns None
missing = config.get("does.not.exist")
# Returns: None
```

### 4. Existence Checks

Check if a configuration key exists:

```python
from config import config

if config.has("cache.redis.url"):
    redis_url = config.get("cache.redis.url")
    # Safe to use redis_url

if not config.has("experimental.feature"):
    print("Experimental feature not configured")
```

### 5. Environment Variable Overrides

Override config values using environment variables in YAML:

```yaml
# cache.yaml
redis:
  url: "${REDIS_URL:redis://localhost:6380}"  # Uses env var or default
  key_prefix: "${REDIS_PREFIX:cache}"
```

```bash
# Terminal
export REDIS_URL="redis://production:6379"
export REDIS_PREFIX="prod_cache"
```

```python
from config import config

redis_url = config.get("cache.redis.url")
# Returns: "redis://production:6379" (from environment)
```

## Integration Examples

### Example 1: Cache Service

```python
from config import config
import redis

class CacheService:
    def __init__(self):
        cache_config = config.get_cache_config()

        # Connect to Redis using config
        self.redis_client = redis.from_url(
            cache_config.redis.url,
            max_connections=cache_config.redis.max_connections,
            decode_responses=True
        )

        # Store TTL map
        self.ttl_map = cache_config.ttl_by_namespace
        self.default_ttl = cache_config.default_ttl

    def cache_document(self, doc_id: str, data: dict) -> None:
        """Cache document with appropriate TTL."""
        ttl = self.ttl_map.get("doc_extract", self.default_ttl)
        key = f"{config.get('cache.redis.key_prefix')}:doc_extract:{doc_id}"
        self.redis_client.setex(key, ttl, json.dumps(data))
```

### Example 2: Rate Limiter

```python
from config import config
from fastapi import Request, HTTPException

class RateLimiter:
    def __init__(self):
        self.rate_limits = config.get_rate_limit_config()

    async def check_rate_limit(self, request: Request) -> None:
        """Check if request is within rate limits."""
        endpoint = request.url.path

        # Get endpoint-specific limits or use default
        limits = self.rate_limits.endpoints.get(
            endpoint,
            self.rate_limits.default
        )

        # Check rate limit (implementation details omitted)
        if self._is_rate_limited(request.client.host, limits):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limits.requests_per_minute}/min"
            )
```

### Example 3: Model Selection

```python
from config import config
from typing import Literal

def get_best_vision_model(
    budget: Literal["low", "medium", "high"] = "medium"
) -> dict:
    """Select vision model based on budget."""
    models_config = config.get_model_registry_config()

    if budget == "low":
        # Cheapest: Gemini Flash
        return models_config.vision_models["gemini-2-5-flash"]
    elif budget == "medium":
        # Balanced: GPT-4o
        return models_config.vision_models["gpt-4o"]
    else:
        # Best quality: Claude Sonnet
        return models_config.vision_models["claude-sonnet-4-5"]

# Usage
model_spec = get_best_vision_model(budget="high")
print(f"Using {model_spec.model_id}")
print(f"Context window: {model_spec.context_window}")
print(f"Cost per 1M input tokens: ${model_spec.cost.input_per_1m}")
```

### Example 4: Circuit Breaker

```python
from config import config
import time

class CircuitBreaker:
    def __init__(self, provider: str):
        cb_config = config.get_circuit_breaker_config()

        # Get provider-specific settings or use defaults
        provider_settings = cb_config.providers.get(provider, {})
        defaults = cb_config.defaults

        self.failure_threshold = (
            provider_settings.failure_threshold or defaults.failure_threshold
        )
        self.timeout = provider_settings.timeout or defaults.timeout
        self.failure_window = (
            provider_settings.failure_window or defaults.failure_window
        )

        self.state = "CLOSED"
        self.failures = []

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if time.time() - self.opened_at > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = []
            return result
        except Exception as e:
            self._record_failure()
            raise
```

## Validation

All configurations are validated on load using Pydantic models. Invalid configs will raise clear validation errors at startup:

```python
# Invalid cache.yaml (negative TTL)
ttl_by_namespace:
  doc_extract: -1  # ERROR!

# Raises ValidationError:
# TTL for 'doc_extract' must be non-negative, got -1
```

## Configuration Files Loaded

The ConfigLoader automatically loads these YAML files:

1. **cache.yaml** - Redis cache configuration and TTLs
2. **rate_limits.yaml** - API endpoint rate limiting
3. **circuit_breaker.yaml** - Fault tolerance for AI providers
4. **models_registry.yaml** - AI model specifications and pricing
5. **computer_use.yaml** - Computer use API settings
6. **vision_config.yaml** - Vision API configuration
7. **document_intelligence_config.yaml** - Document processing settings
8. **entity_resolution_config.yaml** - Entity matching configuration
9. **commitment_priority_config.yaml** - Commitment prioritization rules
10. **storage_config.yaml** - Storage backend configuration

## Testing

Reset the singleton instance for testing:

```python
from config.loader import ConfigLoader

def test_config():
    # Reset for clean test
    ConfigLoader.reset_instance()

    # Get fresh instance
    config = ConfigLoader.get_instance()

    # Run tests...
    assert config.get("cache.default_ttl") == 3600
```

## Best Practices

1. **Use typed configs for complex logic**: `config.get_cache_config()` instead of multiple `config.get()` calls
2. **Provide defaults for optional settings**: `config.get("optional.key", default=value)`
3. **Check existence for conditional features**: `if config.has("feature.enabled")`
4. **Use environment variables for secrets**: `url: "${DATABASE_URL}"` in YAML
5. **Validate early**: Let ConfigLoader fail fast at startup rather than at runtime

## Performance

- **Singleton pattern**: Configs loaded once at startup
- **In-memory cache**: No disk I/O after initialization
- **Lazy imports**: Only load config when first accessed
- **Dot notation overhead**: Negligible (~1μs per lookup)

## Migration from Ad-hoc YAML Loading

Before (scattered throughout codebase):
```python
import yaml

def get_cache_ttl():
    with open("config/cache.yaml") as f:
        config = yaml.safe_load(f)
    return config["ttl_by_namespace"]["doc_extract"]
```

After (centralized):
```python
from config import config

def get_cache_ttl():
    return config.get("cache.ttl_by_namespace.doc_extract")
```

Benefits:
- Single load at startup (not per-function call)
- Pydantic validation (fail fast)
- Type safety with `.get_cache_config()`
- Environment variable support
- Default value handling
