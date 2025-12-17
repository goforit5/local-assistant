"""Anthropic Claude provider."""

import time
from typing import AsyncIterator, Dict, List, Optional
from datetime import datetime

from anthropic import AsyncAnthropic
import anthropic

from .base import BaseProvider, CompletionResponse, Message, ProviderConfig


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude models."""

    PRICING = {
        "claude-sonnet-4-20250514": {
            "input_per_1m": 3.00,
            "output_per_1m": 15.00,
        },
        "claude-opus-4-1-20250805": {
            "input_per_1m": 15.00,
            "output_per_1m": 75.00,
        },
    }

    async def initialize(self) -> None:
        """Initialize Anthropic client."""
        self._client = AsyncAnthropic(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )

    async def chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> CompletionResponse:
        """Send chat completion to Claude."""
        start_time = time.time()

        # Convert messages to Anthropic format
        anthropic_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Extract system message if present
        system = None
        if anthropic_messages and anthropic_messages[0]["role"] == "system":
            system_content = anthropic_messages[0]["content"]
            # System must be a list of content blocks
            system = [{"type": "text", "text": system_content}]
            anthropic_messages = anthropic_messages[1:]

        try:
            # Build request params
            params = {
                "model": model,
                "max_tokens": max_tokens or 8192,
                "temperature": temperature,
                "messages": anthropic_messages,
                **kwargs
            }
            # Only add system if present
            if system:
                params["system"] = system

            response = await self._client.messages.create(**params)

            latency = time.time() - start_time

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

            cost = self.calculate_cost(usage, model)

            return CompletionResponse(
                content=response.content[0].text,
                model=model,
                provider="anthropic",
                usage=usage,
                cost=cost,
                latency=latency,
                timestamp=datetime.now(),
                metadata={"stop_reason": response.stop_reason}
            )

        except anthropic.APIError as e:
            raise Exception(f"Anthropic API error: {e}")

    async def stream_chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream chat completion from Claude."""
        # Convert messages
        anthropic_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        system = None
        if anthropic_messages and anthropic_messages[0]["role"] == "system":
            system = anthropic_messages[0]["content"]
            anthropic_messages = anthropic_messages[1:]

        try:
            async with self._client.messages.stream(
                model=model,
                max_tokens=max_tokens or 8192,
                temperature=temperature,
                system=system,
                messages=anthropic_messages,
                **kwargs
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except anthropic.APIError as e:
            raise Exception(f"Anthropic streaming error: {e}")

    def calculate_cost(self, usage: Dict[str, int], model: str) -> float:
        """Calculate cost for Anthropic models."""
        pricing = self.PRICING.get(model, {"input_per_1m": 3.00, "output_per_1m": 15.00})

        input_cost = (usage["input_tokens"] / 1_000_000) * pricing["input_per_1m"]
        output_cost = (usage["output_tokens"] / 1_000_000) * pricing["output_per_1m"]

        return input_cost + output_cost

    async def close(self) -> None:
        """Clean up Anthropic client."""
        if self._client:
            await self._client.close()
