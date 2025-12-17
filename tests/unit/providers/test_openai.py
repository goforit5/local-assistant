"""Unit tests for OpenAI provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from providers.openai_provider import OpenAIProvider
from providers.base import ProviderConfig, Message


@pytest.fixture
def provider_config():
    """Create provider config."""
    return ProviderConfig(api_key="sk-test-key")


@pytest.fixture
def provider(provider_config):
    """Create OpenAI provider."""
    return OpenAIProvider(provider_config)


class TestOpenAIProvider:
    """Test OpenAIProvider class."""

    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.config.api_key == "sk-test-key"
        assert provider._client is None

    def test_calculate_cost_gpt4o(self, provider):
        """Test cost calculation for GPT-4o."""
        usage = {"input_tokens": 1000, "output_tokens": 2000, "total_tokens": 3000}
        cost = provider.calculate_cost(usage, "gpt-4o")

        # $2.50 per 1M input + $10.00 per 1M output
        expected = (1000 / 1_000_000) * 2.50 + (2000 / 1_000_000) * 10.00
        assert cost == pytest.approx(expected)

    def test_calculate_cost_o1_mini(self, provider):
        """Test cost calculation for o1-mini."""
        usage = {"input_tokens": 1000, "output_tokens": 2000, "total_tokens": 3000}
        cost = provider.calculate_cost(usage, "o1-mini")

        # $3.00 per 1M input + $12.00 per 1M output
        expected = (1000 / 1_000_000) * 3.00 + (2000 / 1_000_000) * 12.00
        assert cost == pytest.approx(expected)

    def test_calculate_cost_unknown_model(self, provider):
        """Test cost calculation with unknown model."""
        usage = {"input_tokens": 1000, "output_tokens": 2000, "total_tokens": 3000}
        cost = provider.calculate_cost(usage, "unknown-model")

        # Should use default pricing (gpt-4o pricing)
        expected = (1000 / 1_000_000) * 2.50 + (2000 / 1_000_000) * 10.00
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_initialize(self, provider):
        """Test provider initialization."""
        with patch('providers.openai_provider.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            await provider.initialize()

            assert provider._client == mock_client
            mock_openai.assert_called_once_with(
                api_key="sk-test-key",
                base_url=None,
                timeout=300,
                max_retries=3
            )

    @pytest.mark.asyncio
    async def test_chat_text_message(self, provider):
        """Test chat with simple text message."""
        messages = [Message(role="user", content="Hello")]

        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Hi there"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.system_fingerprint = "fp_123"

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Set the client before calling chat
        provider._client = mock_client

        response = await provider.chat(messages, model="gpt-4o")

        assert response.content == "Hi there"
        assert response.provider == "openai"
        assert response.model == "gpt-4o"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20
        assert response.usage["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_chat_vision_message(self, provider):
        """Test chat with vision message (structured content)."""
        # Vision message format according to OpenAI docs
        vision_content = [
            {"type": "text", "text": "What's in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
                }
            }
        ]
        messages = [Message(role="user", content=vision_content)]

        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "This is a cat"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 10
        mock_usage.total_tokens = 110

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.system_fingerprint = "fp_456"

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        response = await provider.chat(messages, model="gpt-4o")

        # Verify the vision content was passed correctly
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["messages"][0]["content"] == vision_content
        assert response.content == "This is a cat"

    @pytest.mark.asyncio
    async def test_chat_with_structured_output(self, provider):
        """Test chat with structured output (JSON schema)."""
        messages = [Message(role="user", content="Extract invoice data")]

        # JSON schema for structured output
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "invoice",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "vendor": {"type": "string"},
                        "total": {"type": "number"}
                    },
                    "required": ["vendor", "total"]
                }
            }
        }

        # Mock response with JSON content
        mock_choice = MagicMock()
        mock_choice.message.content = '{"vendor": "ACME Corp", "total": 150.00}'
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 30
        mock_usage.total_tokens = 80

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.system_fingerprint = "fp_789"

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        response = await provider.chat(
            messages,
            model="gpt-4o",
            response_format=response_format
        )

        # Verify response_format was passed to OpenAI
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["response_format"] == response_format
        assert response.content == '{"vendor": "ACME Corp", "total": 150.00}'

    @pytest.mark.asyncio
    async def test_chat_api_error(self, provider):
        """Test chat with API error."""
        import openai

        messages = [Message(role="user", content="Hello")]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )
        provider._client = mock_client

        with pytest.raises(Exception) as exc_info:
            await provider.chat(messages, model="gpt-4o")

        # The provider wraps OpenAI exceptions, but for testing we just check exception is raised
        assert "Rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stream_chat(self, provider):
        """Test streaming chat."""
        messages = [Message(role="user", content="Hello")]

        # Mock streaming response
        async def mock_stream():
            chunks = ["Hello", " there", "!"]
            for chunk in chunks:
                mock_chunk = MagicMock()
                mock_chunk.choices = [MagicMock()]
                mock_chunk.choices[0].delta.content = chunk
                yield mock_chunk

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
        provider._client = mock_client

        result = []
        async for chunk in provider.stream_chat(messages, model="gpt-4o"):
            result.append(chunk)

        assert "".join(result) == "Hello there!"

    @pytest.mark.asyncio
    async def test_close(self, provider):
        """Test provider cleanup."""
        with patch('providers.openai_provider.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_openai.return_value = mock_client

            await provider.initialize()
            await provider.close()

            mock_client.close.assert_called_once()
