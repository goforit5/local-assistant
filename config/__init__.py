"""Centralized configuration management for local_assistant.

This package provides a singleton ConfigLoader that loads all YAML configs
at startup, validates them with Pydantic schemas, and provides convenient
dot-notation access to configuration values.

Quick Start:
    ```python
    from config import config

    # Dot notation access
    ttl = config.get("cache.ttl_by_namespace.doc_extract")

    # Typed config objects
    cache_config = config.get_cache_config()
    ```
"""

from config.loader import ConfigLoader
from config.schemas import (
    CacheConfig,
    CircuitBreakerConfig,
    ModelRegistryConfig,
    RateLimitConfig,
)

# Singleton instance for easy import
config = ConfigLoader.get_instance()

__all__ = [
    'config',
    'ConfigLoader',
    'CacheConfig',
    'CircuitBreakerConfig',
    'ModelRegistryConfig',
    'RateLimitConfig',
]
