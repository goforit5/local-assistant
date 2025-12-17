from typing import Optional, List
from .registry import ServiceRegistry
from .strategies import RoutingStrategy, CompositeStrategy, KeywordStrategy, CapabilityStrategy
from .config import RoutingConfig


class TaskRouter:
    """Routes tasks to appropriate services using pluggable strategies."""

    def __init__(
        self,
        registry: ServiceRegistry,
        strategy: Optional[RoutingStrategy] = None,
        config: Optional[RoutingConfig] = None
    ):
        """
        Initialize task router.

        Args:
            registry: ServiceRegistry instance
            strategy: Routing strategy to use (default: composite of keyword + capability)
            config: RoutingConfig instance
        """
        self._registry = registry
        self._config = config or RoutingConfig()
        self._strategy = strategy or self._create_default_strategy()

    def _create_default_strategy(self) -> RoutingStrategy:
        """Create default composite strategy based on config."""
        strategies: List[RoutingStrategy] = []

        if self._config.use_keyword_matching:
            strategies.append(KeywordStrategy())

        if self._config.use_capability_matching:
            strategies.append(CapabilityStrategy())

        if len(strategies) == 1:
            return strategies[0]

        return CompositeStrategy(strategies)

    def route(self, task_description: str) -> Optional[str]:
        """
        Route a task to the best service.

        Args:
            task_description: Description of the task

        Returns:
            Service name to route to, or None if no suitable service found
        """
        available_services = self._registry.list_services()

        if not available_services:
            return None

        results = self._strategy.route(task_description, available_services)

        if not results:
            return self._config.fallback_service

        best_service, confidence = results[0]

        if confidence < self._config.confidence_threshold:
            return self._config.fallback_service

        return best_service if self._registry.has(best_service) else self._config.fallback_service

    def route_all(self, task_description: str, top_k: int = 3) -> List[str]:
        """
        Route a task to multiple services.

        Args:
            task_description: Description of the task
            top_k: Number of top services to return

        Returns:
            List of service names, sorted by confidence
        """
        available_services = self._registry.list_services()

        if not available_services:
            return []

        results = self._strategy.route(task_description, available_services)

        filtered_results = [
            service for service, confidence in results
            if confidence >= self._config.confidence_threshold and self._registry.has(service)
        ]

        return filtered_results[:top_k]

    def set_strategy(self, strategy: RoutingStrategy) -> None:
        """Update the routing strategy."""
        self._strategy = strategy

    def get_strategy(self) -> RoutingStrategy:
        """Get the current routing strategy."""
        return self._strategy
