"""OpenAI provider."""

import time
from typing import AsyncIterator, Dict, List, Optional
from datetime import datetime

from openai import AsyncOpenAI
import openai

from .base import BaseProvider, CompletionResponse, Message, ProviderConfig


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI models."""

    PRICING = {
        "gpt-4o-2024-11-20": {
            "input_per_1m": 2.50,
            "output_per_1m": 10.00,
        },
        "gpt-4o": {
            "input_per_1m": 2.50,
            "output_per_1m": 10.00,
        },
        "o1-mini-2024-09-12": {
            "input_per_1m": 3.00,
            "output_per_1m": 12.00,
        },
        "o1-mini": {
            "input_per_1m": 3.00,
            "output_per_1m": 12.00,
        },
        "computer-use-preview": {
            "input_per_1m": 2.50,
            "output_per_1m": 10.00,
        },
    }

    async def initialize(self) -> None:
        """Initialize OpenAI client."""
        self._client = AsyncOpenAI(
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
        """Send chat completion to OpenAI.

        Supports structured outputs via response_format parameter:
        - Pass response_format={"type": "json_schema", "json_schema": {...}} for strict schema adherence
        - Pass response_format={"type": "json_object"} for JSON mode (less strict)
        """
        start_time = time.time()

        # Convert messages to OpenAI format
        # Support both string content and structured content (for vision)
        openai_messages = []
        for msg in messages:
            # If content is already a list/dict (vision format), use as-is
            # Otherwise treat as string
            if isinstance(msg.content, (list, dict)):
                openai_messages.append({"role": msg.role, "content": msg.content})
            else:
                openai_messages.append({"role": msg.role, "content": msg.content})

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=openai_messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            latency = time.time() - start_time

            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            cost = self.calculate_cost(usage, model)

            return CompletionResponse(
                content=response.choices[0].message.content,
                model=model,
                provider="openai",
                usage=usage,
                cost=cost,
                latency=latency,
                timestamp=datetime.now(),
                metadata={
                    "finish_reason": response.choices[0].finish_reason,
                    "system_fingerprint": response.system_fingerprint,
                }
            )

        except openai.APIError as e:
            raise Exception(f"OpenAI API error: {e}")

    async def stream_chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream chat completion from OpenAI."""
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                messages=openai_messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                **kwargs
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except openai.APIError as e:
            raise Exception(f"OpenAI streaming error: {e}")

    def calculate_cost(self, usage: Dict[str, int], model: str) -> float:
        """Calculate cost for OpenAI models."""
        pricing = self.PRICING.get(model, {"input_per_1m": 2.50, "output_per_1m": 10.00})

        input_cost = (usage["input_tokens"] / 1_000_000) * pricing["input_per_1m"]
        output_cost = (usage["output_tokens"] / 1_000_000) * pricing["output_per_1m"]

        return input_cost + output_cost

    async def close(self) -> None:
        """Clean up OpenAI client."""
        if self._client:
            await self._client.close()
