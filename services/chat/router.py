"""Smart routing with automatic fallbacks."""

import asyncio
from typing import List, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from providers.base import BaseProvider, CompletionResponse, Message


class RateLimitError(Exception):
    """Raised when rate limit is hit."""
    pass


class ChatRouter:
    """Routes chat requests with smart fallback strategies."""

    def __init__(
        self,
        primary: BaseProvider,
        fallback: Optional[BaseProvider] = None,
        strategy: str = "capability_based",
    ):
        """Initialize router.

        Args:
            primary: Primary provider (e.g., AnthropicProvider)
            fallback: Fallback provider (e.g., GoogleProvider)
            strategy: Routing strategy from config
        """
        self.primary = primary
        self.fallback = fallback
        self.strategy = strategy

    async def chat(
        self,
        messages: List[Message],
        model: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> CompletionResponse:
        """Send chat request with automatic fallback.

        Args:
            messages: List of Message objects
            model: Model name or "auto" for automatic selection
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResponse with content, usage, and cost
        """
        # Determine model based on strategy
        if model == "auto":
            model = self._get_model_for_strategy()

        # Try primary provider
        try:
            response = await self._try_provider(
                self.primary,
                messages,
                model,
                max_tokens,
                temperature,
                **kwargs
            )
            return response
        except (RateLimitError, Exception) as e:
            # Fallback to secondary provider if available
            if self.fallback:
                try:
                    fallback_model = self._get_fallback_model()
                    response = await self._try_provider(
                        self.fallback,
                        messages,
                        fallback_model,
                        max_tokens,
                        temperature,
                        **kwargs
                    )
                    return response
                except Exception as fallback_error:
                    raise Exception(
                        f"Primary failed: {e}, Fallback failed: {fallback_error}"
                    )
            raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def _try_provider(
        self,
        provider: BaseProvider,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int],
        temperature: float,
        **kwargs
    ) -> CompletionResponse:
        """Try to get response from provider with retries."""
        try:
            response = await provider.chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            return response
        except Exception as e:
            # Log the full error for debugging
            print(f"Provider {provider.__class__.__name__} failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

            # Check if it's a rate limit error
            if "rate_limit" in str(e).lower() or "429" in str(e):
                raise RateLimitError(f"Rate limit hit: {e}")
            raise e

    def _get_model_for_strategy(self) -> str:
        """Get model based on routing strategy."""
        # Default to Claude Sonnet for capability-based
        if self.strategy == "capability_based":
            return "claude-sonnet-4-20250514"
        elif self.strategy == "quality_first":
            return "claude-sonnet-4-20250514"
        elif self.strategy == "cost_optimized":
            return "gemini-2.5-flash"
        elif self.strategy == "speed_first":
            return "gemini-2.5-flash"
        else:
            return "claude-sonnet-4-20250514"

    def _get_fallback_model(self) -> str:
        """Get fallback model (typically Gemini)."""
        return "gemini-2.5-flash"

    async def close(self) -> None:
        """Clean up resources."""
        await self.primary.close()
        if self.fallback:
            await self.fallback.close()
