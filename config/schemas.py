"""Pydantic models for configuration validation.

All YAML configs are validated against these schemas at startup.
Provides type safety and clear error messages for configuration issues.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator


class RedisConfig(BaseModel):
    """Redis connection configuration."""
    url: str = Field(default="redis://localhost:6379")
    key_prefix: str = Field(default="cache")
    db: int = Field(default=0, ge=0)
    max_connections: int = Field(default=50, ge=1)
    enable_metrics: bool = Field(default=True)


class ConnectionPoolConfig(BaseModel):
    """Connection pool settings."""
    max_connections: int = Field(default=50, ge=1)
    max_idle_time: int = Field(default=300, ge=0)


class PerformanceConfig(BaseModel):
    """Cache performance tuning."""
    max_object_size: int = Field(default=10485760, ge=1024)
    connection_pool: ConnectionPoolConfig


class MetricsConfig(BaseModel):
    """Metrics tracking configuration."""
    enabled: bool = Field(default=True)
    track_hit_rate: bool = Field(default=True)
    track_latency: bool = Field(default=True)


class FallbackConfig(BaseModel):
    """Cache fallback behavior."""
    log_warning: bool = Field(default=True)
    skip_cache: bool = Field(default=True)
    use_local_cache: bool = Field(default=False)


class CacheConfig(BaseModel):
    """Complete cache configuration schema."""
    redis: RedisConfig
    default_ttl: int = Field(default=3600, ge=0)
    ttl_by_namespace: Dict[str, int] = Field(default_factory=dict)
    invalidation_patterns: Dict[str, str] = Field(default_factory=dict)
    metrics: MetricsConfig
    performance: PerformanceConfig
    fallback: FallbackConfig

    @field_validator('ttl_by_namespace')
    @classmethod
    def validate_ttl_values(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Ensure all TTL values are non-negative."""
        for key, ttl in v.items():
            if ttl < 0:
                raise ValueError(f"TTL for '{key}' must be non-negative, got {ttl}")
        return v


class EndpointRateLimit(BaseModel):
    """Rate limit for a specific endpoint."""
    requests_per_minute: int = Field(ge=1)
    requests_per_hour: int = Field(ge=1)

    @field_validator('requests_per_hour')
    @classmethod
    def validate_hour_greater_than_minute(cls, v: int, info) -> int:
        """Ensure hourly limit is greater than or equal to per-minute limit."""
        if 'requests_per_minute' in info.data:
            if v < info.data['requests_per_minute']:
                raise ValueError(
                    f"requests_per_hour ({v}) must be >= requests_per_minute "
                    f"({info.data['requests_per_minute']})"
                )
        return v


class RateLimitConfig(BaseModel):
    """Rate limiting configuration schema."""
    default: EndpointRateLimit
    endpoints: Dict[str, EndpointRateLimit] = Field(default_factory=dict)


class CircuitBreakerDefaults(BaseModel):
    """Default circuit breaker settings."""
    failure_threshold: int = Field(default=5, ge=1)
    failure_window: int = Field(default=60, ge=1)
    timeout: int = Field(default=30, ge=1)
    half_open_max_calls: int = Field(default=1, ge=1)
    success_threshold: int = Field(default=1, ge=1)
    redis_ttl: int = Field(default=300, ge=1)


class ProviderCircuitBreaker(BaseModel):
    """Provider-specific circuit breaker overrides."""
    failure_threshold: Optional[int] = Field(default=None, ge=1)
    failure_window: Optional[int] = Field(default=None, ge=1)
    timeout: Optional[int] = Field(default=None, ge=1)
    half_open_max_calls: Optional[int] = Field(default=None, ge=1)
    success_threshold: Optional[int] = Field(default=None, ge=1)


class CircuitBreakerRedisConfig(BaseModel):
    """Redis configuration for circuit breaker."""
    url: str = Field(default="redis://localhost:6379")
    key_prefix: str = Field(default="circuit")
    db: int = Field(default=0, ge=0)
    max_connections: int = Field(default=10, ge=1)


class CircuitBreakerConfig(BaseModel):
    """Complete circuit breaker configuration schema."""
    defaults: CircuitBreakerDefaults
    redis: CircuitBreakerRedisConfig
    providers: Dict[str, ProviderCircuitBreaker] = Field(default_factory=dict)


class ModelCost(BaseModel):
    """Model pricing information."""
    input_per_1m: float = Field(ge=0)
    output_per_1m: float = Field(ge=0)
    image_per_1m: Optional[float] = Field(default=None, ge=0)


class ModelDefaults(BaseModel):
    """Default model parameters."""
    max_tokens: int = Field(ge=1)
    temperature: float = Field(ge=0.0, le=2.0)
    timeout: Optional[int] = Field(default=None, ge=1)
    detail: Optional[str] = Field(default=None)
    thinking_budget: Optional[int] = Field(default=None)


class ModelSpec(BaseModel):
    """Individual model specification."""
    model_config = {'protected_namespaces': ()}

    provider: str
    model_id: str
    context_window: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    supports_vision: bool = Field(default=False)
    supports_reasoning: bool = Field(default=False)
    cost: ModelCost
    defaults: ModelDefaults

    @field_validator('max_output_tokens')
    @classmethod
    def validate_output_within_context(cls, v: int, info) -> int:
        """Ensure max_output_tokens doesn't exceed context_window."""
        if 'context_window' in info.data and v > info.data['context_window']:
            raise ValueError(
                f"max_output_tokens ({v}) cannot exceed context_window "
                f"({info.data['context_window']})"
            )
        return v


class ModelRegistryConfig(BaseModel):
    """Complete model registry configuration schema."""
    vision_models: Dict[str, ModelSpec] = Field(default_factory=dict)
    reasoning_models: Dict[str, ModelSpec] = Field(default_factory=dict)

    @field_validator('vision_models')
    @classmethod
    def validate_vision_models(cls, v: Dict[str, ModelSpec]) -> Dict[str, ModelSpec]:
        """Ensure all vision models have supports_vision=True."""
        for name, spec in v.items():
            if not spec.supports_vision:
                raise ValueError(f"Vision model '{name}' must have supports_vision=True")
        return v

    @field_validator('reasoning_models')
    @classmethod
    def validate_reasoning_models(cls, v: Dict[str, ModelSpec]) -> Dict[str, ModelSpec]:
        """Ensure all reasoning models have supports_reasoning=True."""
        for name, spec in v.items():
            if not spec.supports_reasoning:
                raise ValueError(f"Reasoning model '{name}' must have supports_reasoning=True")
        return v
