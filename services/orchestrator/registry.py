from typing import Dict, Any, Optional, List


class ServiceRegistry:
    """Registry pattern for managing available services."""

    def __init__(self, services: Optional[Dict[str, Any]] = None):
        """
        Initialize service registry.

        Args:
            services: Dictionary mapping service names to service instances
        """
        self._services: Dict[str, Any] = services or {}

    def register(self, name: str, service: Any) -> None:
        """Register a service."""
        self._services[name] = service

    def unregister(self, name: str) -> None:
        """Unregister a service."""
        self._services.pop(name, None)

    def get(self, name: str) -> Optional[Any]:
        """Get a service by name."""
        return self._services.get(name)

    def has(self, name: str) -> bool:
        """Check if service exists."""
        return name in self._services

    def list_services(self) -> List[str]:
        """List all registered service names."""
        return list(self._services.keys())

    def get_all(self) -> Dict[str, Any]:
        """Get all services."""
        return self._services.copy()

    def __contains__(self, name: str) -> bool:
        """Support 'in' operator."""
        return name in self._services

    def __len__(self) -> int:
        """Return number of registered services."""
        return len(self._services)

    def __repr__(self) -> str:
        """String representation."""
        service_list = ", ".join(self._services.keys())
        return f"ServiceRegistry(services=[{service_list}])"
