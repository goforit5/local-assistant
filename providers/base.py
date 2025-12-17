"""Base provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    """Standardized message format."""
    role: str
    content: str | List[Dict[str, Any]]  # Support both text and vision formats
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CompletionResponse:
    """Standardized completion response."""
    content: str
    model: str
    provider: str
    usage: Dict[str, int]
    cost: float
    latency: float
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProviderConfig:
    """Provider configuration."""
    api_key: str
    base_url: Optional[str] = None
    timeout: int = 300
    max_retries: int = 3
    rate_limit_per_minute: Optional[int] = None


class BaseProvider(ABC):
    """Base provider interface for AI APIs."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._client: Any = None

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider client."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> CompletionResponse:
        """Send a chat completion request."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a chat completion."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass

    def calculate_cost(self, usage: Dict[str, int], model: str) -> float:
        """Calculate request cost based on token usage."""
        # To be implemented by specific providers
        return 0.0
