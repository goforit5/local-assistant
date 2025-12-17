"""Centralized configuration loader for local_assistant.

Singleton pattern that loads all YAML configs at startup, validates with Pydantic,
and provides dot-notation access to nested config values.

Example Usage:
    ```python
    from config.loader import ConfigLoader

    # Get singleton instance (loads all configs on first call)
    config = ConfigLoader.get_instance()

    # Dot notation access to nested values
    doc_extract_ttl = config.get("cache.ttl_by_namespace.doc_extract")
    # Returns: 604800

    vision_rate_limit = config.get("rate_limits.endpoints./api/vision.requests_per_minute")
    # Returns: 10

    anthropic_threshold = config.get("circuit_breaker.providers.anthropic.failure_threshold")
    # Returns: 5

    # Get typed config objects
    cache_config = config.get_cache_config()  # Returns CacheConfig instance
    rate_limits = config.get_rate_limit_config()  # Returns RateLimitConfig instance

    # Environment variable override (in YAML: "${REDIS_URL}")
    redis_url = config.get("cache.redis.url")
    # Uses environment variable REDIS_URL if set, otherwise uses YAML default

    # Get with default value
    custom_ttl = config.get("cache.ttl_by_namespace.unknown", default=3600)
    # Returns: 3600 (default value)

    # Access all models
    vision_models = config.get("models_registry.vision_models")
    claude_spec = config.get("models_registry.vision_models.claude-sonnet-4-5")
    ```

Design Decisions:
    - Singleton pattern: Single source of truth, loaded once
    - Eager loading: All configs validated at startup (fail fast)
    - Immutable: Configs cached in memory, not reloaded during runtime
    - Environment overrides: ${VAR} syntax replaced with os.environ values
    - Pydantic validation: Type safety and clear error messages
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import ValidationError

from config.schemas import (
    CacheConfig,
    CircuitBreakerConfig,
    ModelRegistryConfig,
    RateLimitConfig,
)


class ConfigLoader:
    """Singleton configuration loader with validation and dot-notation access."""

    _instance: Optional['ConfigLoader'] = None
    _initialized: bool = False

    def __init__(self):
        """Initialize ConfigLoader. Use get_instance() instead."""
        if ConfigLoader._initialized:
            return

        self._config_dir = Path(__file__).parent
        self._configs: Dict[str, Any] = {}
        self._load_all_configs()
        ConfigLoader._initialized = True

    @classmethod
    def get_instance(cls) -> 'ConfigLoader':
        """Get singleton instance of ConfigLoader.

        Returns:
            ConfigLoader: The singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance. Used for testing only."""
        cls._instance = None
        cls._initialized = False

    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load and parse YAML file with environment variable substitution.

        Args:
            file_path: Path to YAML file.

        Returns:
            Parsed YAML content as dictionary.

        Raises:
            FileNotFoundError: If YAML file doesn't exist.
            yaml.YAMLError: If YAML is malformed.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with open(file_path, 'r') as f:
            content = f.read()

        # Replace environment variables: ${VAR_NAME} or ${VAR_NAME:default}
        def replace_env_var(match):
            var_expr = match.group(1)
            if ':' in var_expr:
                var_name, default = var_expr.split(':', 1)
                return os.environ.get(var_name.strip(), default.strip())
            else:
                var_name = var_expr.strip()
                if var_name not in os.environ:
                    raise ValueError(
                        f"Environment variable '{var_name}' not found in {file_path}"
                    )
                return os.environ[var_name]

        content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)

        return yaml.safe_load(content)

    def _load_all_configs(self) -> None:
        """Load all YAML configuration files and validate with Pydantic schemas.

        Raises:
            ValidationError: If any config fails Pydantic validation.
            FileNotFoundError: If required config file is missing.
        """
        # Load core configs with validation
        try:
            cache_data = self._load_yaml(self._config_dir / "cache.yaml")
            self._configs['cache'] = CacheConfig(**cache_data)
        except ValidationError as e:
            raise ValidationError(f"Invalid cache.yaml: {e}") from e

        try:
            rate_limit_data = self._load_yaml(self._config_dir / "rate_limits.yaml")
            self._configs['rate_limits'] = RateLimitConfig(**rate_limit_data)
        except ValidationError as e:
            raise ValidationError(f"Invalid rate_limits.yaml: {e}") from e

        try:
            circuit_breaker_data = self._load_yaml(self._config_dir / "circuit_breaker.yaml")
            self._configs['circuit_breaker'] = CircuitBreakerConfig(**circuit_breaker_data)
        except ValidationError as e:
            raise ValidationError(f"Invalid circuit_breaker.yaml: {e}") from e

        try:
            models_data = self._load_yaml(self._config_dir / "models_registry.yaml")
            self._configs['models_registry'] = ModelRegistryConfig(**models_data)
        except ValidationError as e:
            raise ValidationError(f"Invalid models_registry.yaml: {e}") from e

        # Load additional configs without strict validation (for extensibility)
        additional_configs = [
            "computer_use.yaml",
            "vision_config.yaml",
            "document_intelligence_config.yaml",
            "entity_resolution_config.yaml",
            "commitment_priority_config.yaml",
            "storage_config.yaml",
        ]

        for config_file in additional_configs:
            config_path = self._config_dir / config_file
            if config_path.exists():
                config_key = config_file.replace('.yaml', '').replace('_config', '')
                self._configs[config_key] = self._load_yaml(config_path)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to config value (e.g., "cache.redis.url").
            default: Default value if key path not found.

        Returns:
            Configuration value at key_path, or default if not found.

        Example:
            >>> config.get("cache.ttl_by_namespace.doc_extract")
            604800
            >>> config.get("cache.redis.url")
            "redis://localhost:6380"
            >>> config.get("nonexistent.key", default="fallback")
            "fallback"
        """
        keys = key_path.split('.')
        value = self._configs

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif hasattr(value, key):
                value = getattr(value, key)
            elif hasattr(value, 'model_dump'):
                # Pydantic model - convert to dict
                value = value.model_dump().get(key)
            else:
                return default

            if value is None:
                return default

        return value

    def get_cache_config(self) -> CacheConfig:
        """Get validated cache configuration.

        Returns:
            CacheConfig: Validated cache configuration object.
        """
        return self._configs['cache']

    def get_rate_limit_config(self) -> RateLimitConfig:
        """Get validated rate limit configuration.

        Returns:
            RateLimitConfig: Validated rate limit configuration object.
        """
        return self._configs['rate_limits']

    def get_circuit_breaker_config(self) -> CircuitBreakerConfig:
        """Get validated circuit breaker configuration.

        Returns:
            CircuitBreakerConfig: Validated circuit breaker configuration object.
        """
        return self._configs['circuit_breaker']

    def get_model_registry_config(self) -> ModelRegistryConfig:
        """Get validated model registry configuration.

        Returns:
            ModelRegistryConfig: Validated model registry configuration object.
        """
        return self._configs['models_registry']

    def get_all_configs(self) -> Dict[str, Any]:
        """Get all loaded configurations.

        Returns:
            Dictionary of all configuration objects.
        """
        return self._configs.copy()

    def has(self, key_path: str) -> bool:
        """Check if configuration key exists.

        Args:
            key_path: Dot-separated path to config value.

        Returns:
            True if key exists, False otherwise.
        """
        return self.get(key_path) is not None

    def __repr__(self) -> str:
        """String representation of ConfigLoader."""
        config_keys = list(self._configs.keys())
        return f"ConfigLoader(configs={config_keys})"
