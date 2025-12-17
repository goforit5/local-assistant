"""Streaming handler for real-time responses."""

import time
from typing import AsyncIterator, List, Optional
from datetime import datetime

from providers.base import BaseProvider, CompletionResponse, Message


class StreamHandler:
    """Handles streaming chat responses."""

    def __init__(self, router):
        """Initialize stream handler.

        Args:
            router: ChatRouter instance for provider access
        """
        self.router = router

    async def stream_chat(
        self,
        messages: List[Message],
        model: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream chat response with automatic fallback.

        Args:
            messages: List of Message objects
            model: Model name or "auto"
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Yields:
            Text chunks as they arrive
        """
        # Get model based on strategy
        if model == "auto":
            model = self.router._get_model_for_strategy()

        # Try streaming from primary provider
        try:
            async for chunk in self.router.primary.stream_chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            ):
                yield chunk
        except Exception as e:
            # Fall back to non-streaming on error
            response = await self.router.chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            yield response.content

    async def stream_with_response(
        self,
        messages: List[Message],
        model: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> tuple[AsyncIterator[str], CompletionResponse]:
        """Stream response and return final CompletionResponse.

        This aggregates chunks to build a final response object with
        usage statistics and cost information.

        Args:
            messages: List of Message objects
            model: Model name or "auto"
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            Tuple of (chunk iterator, final CompletionResponse)
        """
        # Get model
        if model == "auto":
            model = self.router._get_model_for_strategy()

        start_time = time.time()
        chunks = []

        # Stream and collect chunks
        try:
            async for chunk in self.router.primary.stream_chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            ):
                chunks.append(chunk)
                yield chunk
        except Exception:
            # Fall back to regular response
            response = await self.router.chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            yield response.content
            return

        # Build final response
        full_content = "".join(chunks)
        latency = time.time() - start_time

        # Estimate usage (this is approximate for streaming)
        estimated_input_tokens = sum(len(m.content.split()) * 1.3 for m in messages)
        estimated_output_tokens = len(full_content.split()) * 1.3

        usage = {
            "input_tokens": int(estimated_input_tokens),
            "output_tokens": int(estimated_output_tokens),
            "total_tokens": int(estimated_input_tokens + estimated_output_tokens),
        }

        cost = self.router.primary.calculate_cost(usage, model)

        response = CompletionResponse(
            content=full_content,
            model=model,
            provider=self.router.primary.__class__.__name__.replace("Provider", "").lower(),
            usage=usage,
            cost=cost,
            latency=latency,
            timestamp=datetime.now(),
            metadata={"streaming": True},
        )

        # Can't return value from async generator
        return
