"""Provider factory with registry pattern and intelligent routing.

Design Pattern: Factory + Registry + Strategy
- Registry: Auto-register providers via @register_provider decorator
- Factory: create_provider() creates instances by name
- Strategy: Route requests based on cost, capability, or explicit selection

Usage Example:
    ```python
    from providers.factory import ProviderFactory
    from providers.base import Message

    # Initialize factory (lazy loads providers)
    factory = ProviderFactory()
    await factory.initialize()

    # Create specific provider
    provider = await factory.create_provider("anthropic")
    response = await provider.chat(
        messages=[Message(role="user", content="Hello")],
        model="claude-sonnet-4-5-20250929"
    )

    # Get default provider based on routing strategy
    provider = await factory.get_default_provider(task_type="vision")

    # Cost-based routing for budget optimization
    provider = await factory.get_cheapest_provider(task_type="reasoning")

    # Inject circuit breaker for fault tolerance
    from lib.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

    cb = CircuitBreaker("anthropic", CircuitBreakerConfig())
    await cb.initialize()
    factory.set_circuit_breaker("anthropic", cb)

    # Cleanup
    await factory.close_all()
    ```

Architecture:
    - Singleton registry for all providers
    - Lazy initialization (create on first use)
    - Config-driven routing via models_registry.yaml
    - Circuit breaker injection for resilience
    - Thread-safe provider caching
"""

import os
from typing import Dict, Optional, Type, List
from pathlib import Path
import yaml
import asyncio

from .base import BaseProvider, ProviderConfig
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from lib.circuit_breaker import CircuitBreaker

# Optional Google provider
try:
    from .google_provider import GoogleProvider
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


class ProviderRegistry:
    """Registry for provider classes with auto-registration."""

    _providers: Dict[str, Type[BaseProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[BaseProvider]) -> None:
        """Register a provider class."""
        cls._providers[name] = provider_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseProvider]]:
        """Get a provider class by name."""
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())


def register_provider(name: str):
    """
    Decorator to auto-register provider classes.

    Usage:
        @register_provider("anthropic")
        class AnthropicProvider(BaseProvider):
            pass
    """
    def decorator(provider_class: Type[BaseProvider]) -> Type[BaseProvider]:
        ProviderRegistry.register(name, provider_class)
        return provider_class
    return decorator


class ProviderFactory:
    """
    Factory for creating and managing AI provider instances.

    Features:
    - Lazy initialization of providers
    - Config-driven provider selection
    - Cost-based routing
    - Circuit breaker injection
    - Thread-safe caching
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the provider factory.

        Args:
            config_path: Path to models_registry.yaml (defaults to config/models_registry.yaml)
        """
        self._instances: Dict[str, BaseProvider] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._config: Dict = {}
        self._lock = asyncio.Lock()
        self._initialized = False

        # Determine config path
        if config_path is None:
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config" / "models_registry.yaml"

        self.config_path = Path(config_path)

        # Auto-register built-in providers
        ProviderRegistry.register("anthropic", AnthropicProvider)
        ProviderRegistry.register("openai", OpenAIProvider)
        if GOOGLE_AVAILABLE:
            ProviderRegistry.register("google", GoogleProvider)

    async def initialize(self) -> None:
        """Load configuration from models_registry.yaml."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            try:
                with open(self.config_path) as f:
                    self._config = yaml.safe_load(f)
                self._initialized = True
            except Exception as e:
                raise RuntimeError(f"Failed to load models registry: {e}")

    def _get_api_key(self, provider_name: str) -> str:
        """
        Get API key for provider from environment variables.

        Args:
            provider_name: Provider name (anthropic, openai, google)

        Returns:
            API key from environment

        Raises:
            ValueError: If API key not found
        """
        key_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }

        env_var = key_map.get(provider_name)
        if not env_var:
            raise ValueError(f"Unknown provider: {provider_name}")

        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(f"API key not found for {provider_name}. Set {env_var} in .env")

        return api_key

    async def create_provider(
        self,
        name: str,
        config: Optional[ProviderConfig] = None,
        cache: bool = True
    ) -> BaseProvider:
        """
        Create or retrieve a provider instance.

        Args:
            name: Provider name (anthropic, openai, google)
            config: Optional provider configuration (uses defaults if None)
            cache: If True, cache and reuse provider instances

        Returns:
            Initialized provider instance

        Raises:
            ValueError: If provider not registered or API key missing
        """
        # Return cached instance if available
        if cache and name in self._instances:
            return self._instances[name]

        # Get provider class from registry
        provider_class = ProviderRegistry.get(name)
        if not provider_class:
            available = ", ".join(ProviderRegistry.list_providers())
            raise ValueError(
                f"Provider '{name}' not registered. Available: {available}"
            )

        # Create config if not provided
        if config is None:
            api_key = self._get_api_key(name)
            config = ProviderConfig(
                api_key=api_key,
                timeout=300,
                max_retries=3
            )

        # Create provider instance
        provider = provider_class(config)
        await provider.initialize()

        # Cache if requested
        if cache:
            async with self._lock:
                self._instances[name] = provider

        return provider

    async def get_default_provider(
        self,
        task_type: Optional[str] = None
    ) -> BaseProvider:
        """
        Get default provider based on routing strategy.

        Args:
            task_type: Optional task type (vision, reasoning). If None, returns cheapest.

        Returns:
            Provider instance for the task type

        Routing Logic:
            - vision: Cheapest vision-capable model (gemini-2-5-flash)
            - reasoning: Best quality reasoning model (claude-opus-4-1)
            - None: Cheapest overall (gemini-2-5-flash)
        """
        await self.initialize()

        if task_type == "vision":
            # Use cheapest vision model: gemini-2-5-flash
            return await self.create_provider("google")
        elif task_type == "reasoning":
            # Use best reasoning model: claude-opus-4-1
            return await self.create_provider("anthropic")
        else:
            # Default to cheapest: gemini-2-5-flash
            return await self.create_provider("google")

    async def get_cheapest_provider(
        self,
        task_type: Optional[str] = None
    ) -> BaseProvider:
        """
        Get cheapest provider for a given task type.

        Args:
            task_type: Task type (vision, reasoning). If None, returns overall cheapest.

        Returns:
            Cheapest provider instance
        """
        await self.initialize()

        # Scan models_registry.yaml for cheapest option
        min_cost = float('inf')
        cheapest_provider = None

        model_sections = []
        if task_type == "vision":
            model_sections = [self._config.get("vision_models", {})]
        elif task_type == "reasoning":
            model_sections = [self._config.get("reasoning_models", {})]
        else:
            model_sections = [
                self._config.get("vision_models", {}),
                self._config.get("reasoning_models", {})
            ]

        for section in model_sections:
            for model_name, model_info in section.items():
                cost = model_info.get("cost", {})
                input_cost = cost.get("input_per_1m", 0)
                output_cost = cost.get("output_per_1m", 0)

                # Estimate total cost (weighted average: 60% input, 40% output)
                avg_cost = (0.6 * input_cost) + (0.4 * output_cost)

                if avg_cost < min_cost:
                    min_cost = avg_cost
                    cheapest_provider = model_info.get("provider")

        if not cheapest_provider:
            # Fallback to Google as cheapest
            cheapest_provider = "google"

        return await self.create_provider(cheapest_provider)

    def set_circuit_breaker(self, provider_name: str, circuit_breaker: CircuitBreaker) -> None:
        """
        Inject circuit breaker for a provider.

        Args:
            provider_name: Provider name
            circuit_breaker: Initialized CircuitBreaker instance
        """
        self._circuit_breakers[provider_name] = circuit_breaker

    def get_circuit_breaker(self, provider_name: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker for a provider.

        Args:
            provider_name: Provider name

        Returns:
            CircuitBreaker instance or None if not set
        """
        return self._circuit_breakers.get(provider_name)

    async def close_all(self) -> None:
        """Close all provider instances and circuit breakers."""
        async with self._lock:
            # Close all providers
            for provider in self._instances.values():
                try:
                    await provider.close()
                except Exception:
                    pass

            # Close all circuit breakers
            for cb in self._circuit_breakers.values():
                try:
                    await cb.close()
                except Exception:
                    pass

            self._instances.clear()
            self._circuit_breakers.clear()

    def list_available_providers(self) -> List[str]:
        """List all available provider names."""
        return ProviderRegistry.list_providers()

    def get_provider_models(self, task_type: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get available models grouped by provider.

        Args:
            task_type: Optional task type filter (vision, reasoning)

        Returns:
            Dict mapping provider names to list of model IDs
        """
        if not self._initialized:
            return {}

        result: Dict[str, List[str]] = {}

        sections = []
        if task_type == "vision":
            sections = [("vision_models", self._config.get("vision_models", {}))]
        elif task_type == "reasoning":
            sections = [("reasoning_models", self._config.get("reasoning_models", {}))]
        else:
            sections = [
                ("vision_models", self._config.get("vision_models", {})),
                ("reasoning_models", self._config.get("reasoning_models", {}))
            ]

        for section_name, section in sections:
            for model_name, model_info in section.items():
                provider = model_info.get("provider")
                model_id = model_info.get("model_id")

                if provider and model_id:
                    if provider not in result:
                        result[provider] = []
                    result[provider].append(model_id)

        return result
