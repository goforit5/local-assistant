"""OpenAI Responses API client wrapper for computer use."""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from openai import AsyncOpenAI
import openai
from openai.types.responses import (
    Response,
    ResponseStreamEvent,
    ComputerTool,
)

from providers.base import ProviderConfig


class ResponsesClient:
    """Client for OpenAI Responses API with computer use capabilities."""

    def __init__(self, config: ProviderConfig):
        """Initialize Responses API client.

        Args:
            config: Provider configuration with API key and settings
        """
        self.config = config
        self._client: Optional[AsyncOpenAI] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize OpenAI client."""
        self._client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        self._initialized = True

    async def create_response(
        self,
        input_text: str,
        model: str = "computer-use-preview",
        environment: str = "browser",
        display_width: int = 1920,
        display_height: int = 1080,
        reasoning: str = "concise",
        truncation: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        conversation: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a response using OpenAI Responses API.

        Args:
            input_text: User input text
            model: Model name (default: computer-use-preview)
            environment: Environment type (browser or desktop)
            display_width: Display width in pixels
            display_height: Display height in pixels
            reasoning: Reasoning mode (concise or detailed)
            truncation: Truncation strategy (auto)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            conversation: Optional conversation history
            **kwargs: Additional parameters

        Returns:
            Dictionary containing response data and metadata
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()

        # Build computer use tool configuration
        computer_tool: ComputerTool = {
            "type": "computer_use_preview",
            "display_width": display_width,
            "display_height": display_height,
            "environment": environment,
        }

        # Build input messages
        input_messages = [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": input_text}]
            }
        ]

        # Add conversation history if provided
        if conversation:
            input_messages = conversation + input_messages

        try:
            # Create response via Responses API
            response: Response = await self._client.responses.create(
                model=model,
                tools=[computer_tool],
                input=input_messages,
                reasoning={"summary": reasoning},
                truncation=truncation,
                max_output_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            latency = time.time() - start_time

            # Extract response data
            result = {
                "response_id": response.id,
                "status": response.status,
                "model": model,
                "environment": environment,
                "latency": latency,
                "timestamp": datetime.now(),
                "output": self._extract_output(response),
                "tool_calls": self._extract_tool_calls(response),
                "usage": self._extract_usage(response),
                "metadata": {
                    "created_at": response.created_at,
                    "object": response.object,
                }
            }

            return result

        except openai.APIError as e:
            raise Exception(f"OpenAI Responses API error: {e}")

    async def retrieve_response(
        self,
        response_id: str,
        include: Optional[List[str]] = None
    ) -> Response:
        """Retrieve a response by ID.

        Args:
            response_id: Response identifier
            include: Optional list of items to include

        Returns:
            Response object
        """
        if not self._initialized:
            await self.initialize()

        try:
            params = {}
            if include:
                params["include"] = include

            response = await self._client.responses.retrieve(
                response_id=response_id,
                **params
            )
            return response

        except openai.APIError as e:
            raise Exception(f"Failed to retrieve response: {e}")

    async def cancel_response(self, response_id: str) -> Response:
        """Cancel an in-progress response.

        Args:
            response_id: Response identifier

        Returns:
            Cancelled response object
        """
        if not self._initialized:
            await self.initialize()

        try:
            response = await self._client.responses.cancel(response_id=response_id)
            return response

        except openai.APIError as e:
            raise Exception(f"Failed to cancel response: {e}")

    async def delete_response(self, response_id: str) -> None:
        """Delete a response.

        Args:
            response_id: Response identifier
        """
        if not self._initialized:
            await self.initialize()

        try:
            await self._client.responses.delete(response_id=response_id)

        except openai.APIError as e:
            raise Exception(f"Failed to delete response: {e}")

    def _extract_output(self, response: Response) -> List[Dict[str, Any]]:
        """Extract output items from response.

        Args:
            response: Response object

        Returns:
            List of output items
        """
        output_items = []

        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'type'):
                    if item.type == "message":
                        output_items.append({
                            "type": "message",
                            "role": getattr(item, 'role', None),
                            "content": getattr(item, 'content', None),
                        })
                    elif item.type == "text":
                        output_items.append({
                            "type": "text",
                            "text": getattr(item, 'text', None),
                        })

        return output_items

    def _extract_tool_calls(self, response: Response) -> List[Dict[str, Any]]:
        """Extract computer use tool calls from response.

        Args:
            response: Response object

        Returns:
            List of tool call actions
        """
        tool_calls = []

        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'type') and 'tool_call' in str(item.type):
                    if hasattr(item, 'computer_use_preview'):
                        tool_call_data = item.computer_use_preview
                        tool_calls.append({
                            "type": "computer_use",
                            "action": getattr(tool_call_data, 'action', None),
                            "coordinate": getattr(tool_call_data, 'coordinate', None),
                            "text": getattr(tool_call_data, 'text', None),
                            "output": getattr(item, 'output', None),
                        })

        return tool_calls

    def _extract_usage(self, response: Response) -> Dict[str, int]:
        """Extract token usage from response.

        Args:
            response: Response object

        Returns:
            Dictionary with token usage
        """
        if hasattr(response, 'usage') and response.usage:
            return {
                "input_tokens": getattr(response.usage, 'input_tokens', 0),
                "output_tokens": getattr(response.usage, 'output_tokens', 0),
                "total_tokens": getattr(response.usage, 'total_tokens', 0),
            }
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    async def close(self) -> None:
        """Clean up OpenAI client resources."""
        if self._client:
            await self._client.close()
            self._initialized = False
