"""Unit tests for ChatRouter."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from services.chat import ChatRouter
from services.chat.router import RateLimitError
from providers.base import Message, CompletionResponse


@pytest.fixture
def mock_primary_provider():
    """Create mock primary provider."""
    provider = MagicMock()
    provider.chat = AsyncMock()
    provider.close = AsyncMock()
    return provider


@pytest.fixture
def mock_fallback_provider():
    """Create mock fallback provider."""
    provider = MagicMock()
    provider.chat = AsyncMock()
    provider.close = AsyncMock()
    return provider


@pytest.fixture
def router(mock_primary_provider, mock_fallback_provider):
    """Create chat router."""
    return ChatRouter(
        primary=mock_primary_provider,
        fallback=mock_fallback_provider,
        strategy="capability_based"
    )


class TestChatRouter:
    """Test ChatRouter class."""

    def test_initialization(self, router, mock_primary_provider):
        """Test router initialization."""
        assert router.primary == mock_primary_provider
        assert router.strategy == "capability_based"

    @pytest.mark.asyncio
    async def test_chat_with_primary_success(self, router, mock_primary_provider):
        """Test successful chat with primary provider."""
        expected_response = CompletionResponse(
            content="Hello!",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            cost=0.001,
            latency=0.5,
            timestamp=datetime.now()
        )
        mock_primary_provider.chat.return_value = expected_response

        messages = [Message(role="user", content="Hi")]
        response = await router.chat(messages)

        assert response == expected_response
        mock_primary_provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_fallback_on_rate_limit(
        self, router, mock_primary_provider, mock_fallback_provider
    ):
        """Test fallback on rate limit."""
        # Primary fails with rate limit
        mock_primary_provider.chat.side_effect = RateLimitError("Rate limited")

        # Fallback succeeds
        fallback_response = CompletionResponse(
            content="Fallback response",
            model="gemini-2.5-flash-latest",
            provider="google",
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            cost=0.0001,
            latency=0.3,
            timestamp=datetime.now()
        )
        mock_fallback_provider.chat.return_value = fallback_response

        messages = [Message(role="user", content="Hi")]
        response = await router.chat(messages)

        assert response == fallback_response
        mock_fallback_provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_failure_without_fallback(self, mock_primary_provider):
        """Test failure when no fallback available."""
        router = ChatRouter(primary=mock_primary_provider, fallback=None)
        mock_primary_provider.chat.side_effect = Exception("API Error")

        messages = [Message(role="user", content="Hi")]

        with pytest.raises(Exception, match="API Error"):
            await router.chat(messages)

    def test_get_model_for_strategy(self, router):
        """Test model selection based on strategy."""
        model = router._get_model_for_strategy()
        assert model == "claude-sonnet-4-20250514"

        router.strategy = "cost_optimized"
        model = router._get_model_for_strategy()
        assert model == "gemini-2.5-flash-latest"
