"""Google Gemini provider."""

import time
from typing import AsyncIterator, Dict, List, Optional
from datetime import datetime

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from .base import BaseProvider, CompletionResponse, Message, ProviderConfig


class GoogleProvider(BaseProvider):
    """Provider for Google Gemini models."""

    PRICING = {
        "gemini-2.5-flash-latest": {
            "input_per_1m": 0.075,
            "output_per_1m": 0.30,
        },
        "gemini-2.5-flash": {
            "input_per_1m": 0.075,
            "output_per_1m": 0.30,
        },
        "gemini-2.5-pro": {
            "input_per_1m": 0.25,
            "output_per_1m": 1.00,
        },
    }

    async def initialize(self) -> None:
        """Initialize Google Gemini client."""
        genai.configure(api_key=self.config.api_key)
        self._client = genai

    async def chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> CompletionResponse:
        """Send chat completion to Gemini."""
        start_time = time.time()

        # Initialize model
        gemini_model = genai.GenerativeModel(model)

        # Convert messages to Gemini format
        # Gemini uses a different structure - need to handle system messages differently
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [msg.content]})

        # Create generation config
        generation_config = GenerationConfig(
            max_output_tokens=max_tokens or 8192,
            temperature=temperature,
        )

        try:
            response = await gemini_model.generate_content_async(
                contents=contents,
                generation_config=generation_config,
            )

            latency = time.time() - start_time

            # Gemini doesn't always provide detailed token counts
            usage = {
                "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            }

            cost = self.calculate_cost(usage, model)

            return CompletionResponse(
                content=response.text,
                model=model,
                provider="google",
                usage=usage,
                cost=cost,
                latency=latency,
                timestamp=datetime.now(),
                metadata={
                    "finish_reason": response.candidates[0].finish_reason if response.candidates else None,
                }
            )

        except Exception as e:
            raise Exception(f"Google Gemini API error: {e}")

    async def stream_chat(
        self,
        messages: List[Message],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream chat completion from Gemini."""
        gemini_model = genai.GenerativeModel(model)

        contents = []
        for msg in messages:
            if msg.role != "system":
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [msg.content]})

        generation_config = GenerationConfig(
            max_output_tokens=max_tokens or 8192,
            temperature=temperature,
        )

        try:
            response = await gemini_model.generate_content_async(
                contents=contents,
                generation_config=generation_config,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            raise Exception(f"Google Gemini streaming error: {e}")

    def calculate_cost(self, usage: Dict[str, int], model: str) -> float:
        """Calculate cost for Gemini models."""
        pricing = self.PRICING.get(model, {"input_per_1m": 0.075, "output_per_1m": 0.30})

        input_cost = (usage["input_tokens"] / 1_000_000) * pricing["input_per_1m"]
        output_cost = (usage["output_tokens"] / 1_000_000) * pricing["output_per_1m"]

        return input_cost + output_cost

    async def close(self) -> None:
        """Clean up Gemini client."""
        # Gemini SDK doesn't require explicit cleanup
        pass
