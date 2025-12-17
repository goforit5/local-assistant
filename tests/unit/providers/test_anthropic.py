"""Unit tests for Anthropic provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from providers.anthropic_provider import AnthropicProvider
from providers.base import ProviderConfig, Message


@pytest.fixture
def provider_config():
    """Create provider config."""
    return ProviderConfig(api_key="sk-ant-test")


@pytest.fixture
def provider(provider_config):
    """Create Anthropic provider."""
    return AnthropicProvider(provider_config)


class TestAnthropicProvider:
    """Test AnthropicProvider class."""

    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.config.api_key == "sk-ant-test"
        assert provider._client is None

    def test_calculate_cost(self, provider):
        """Test cost calculation."""
        usage = {"input_tokens": 1000, "output_tokens": 2000}
        cost = provider.calculate_cost(usage, "claude-sonnet-4-20250514")

        # $3.00 per 1M input + $15.00 per 1M output
        expected = (1000 / 1_000_000) * 3.00 + (2000 / 1_000_000) * 15.00
        assert cost == pytest.approx(expected)

    def test_calculate_cost_unknown_model(self, provider):
        """Test cost calculation with unknown model."""
        usage = {"input_tokens": 1000, "output_tokens": 2000}
        cost = provider.calculate_cost(usage, "unknown-model")

        # Should use default pricing
        expected = (1000 / 1_000_000) * 3.00 + (2000 / 1_000_000) * 15.00
        assert cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_chat_message_conversion(self, provider):
        """Test message format conversion."""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]

        # Mock the client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_response.stop_reason = "end_turn"

        with patch.object(provider, '_client', create=True) as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            await provider.initialize()
            response = await provider.chat(messages, model="claude-sonnet-4-20250514")

            assert response.content == "Response"
            assert response.provider == "anthropic"
