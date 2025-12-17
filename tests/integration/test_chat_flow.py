"""Integration tests for complete chat flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from services.chat import ChatRouter, ChatSession
from providers.base import Message, CompletionResponse


@pytest.fixture
def mock_router():
    """Create mock router."""
    router = MagicMock()
    router.chat = AsyncMock()
    router.close = AsyncMock()
    return router


@pytest.fixture
def chat_session(mock_router):
    """Create chat session."""
    return ChatSession(
        conversation_id="test-conv-123",
        router=mock_router,
        memory_store=None
    )


class TestChatFlow:
    """Test complete chat flow integration."""

    @pytest.mark.asyncio
    async def test_send_message_updates_history(self, chat_session, mock_router):
        """Test that sending message updates history."""
        response = CompletionResponse(
            content="Hello! How can I help?",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            cost=0.001,
            latency=0.5,
            timestamp=datetime.now()
        )
        mock_router.chat.return_value = response

        result = await chat_session.send_message("Hi")

        assert result == response
        assert len(chat_session.messages) == 2  # User + assistant
        assert chat_session.messages[0].role == "user"
        assert chat_session.messages[0].content == "Hi"
        assert chat_session.messages[1].role == "assistant"
        assert chat_session.messages[1].content == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_session_cost_tracking(self, chat_session, mock_router):
        """Test session-level cost tracking."""
        response1 = CompletionResponse(
            content="Response 1",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            cost=0.001,
            latency=0.5,
            timestamp=datetime.now()
        )
        response2 = CompletionResponse(
            content="Response 2",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            usage={"input_tokens": 15, "output_tokens": 25, "total_tokens": 40},
            cost=0.0015,
            latency=0.6,
            timestamp=datetime.now()
        )
        mock_router.chat.side_effect = [response1, response2]

        await chat_session.send_message("Message 1")
        await chat_session.send_message("Message 2")

        assert chat_session.total_cost == pytest.approx(0.0025)
        assert chat_session.total_tokens == 70

    @pytest.mark.asyncio
    async def test_get_history(self, chat_session, mock_router):
        """Test retrieving conversation history."""
        response = CompletionResponse(
            content="Response",
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            cost=0.001,
            latency=0.5,
            timestamp=datetime.now()
        )
        mock_router.chat.return_value = response

        await chat_session.send_message("Message 1")
        await chat_session.send_message("Message 2")

        history = await chat_session.get_history(limit=10)
        assert len(history) == 4  # 2 user + 2 assistant messages

    def test_cost_summary(self, chat_session):
        """Test cost summary generation."""
        chat_session.total_cost = 0.05
        chat_session.total_tokens = 1000
        chat_session.messages = [MagicMock()] * 10

        summary = chat_session.get_cost_summary()

        assert summary["conversation_id"] == "test-conv-123"
        assert summary["total_cost"] == 0.05
        assert summary["total_tokens"] == 1000
        assert summary["message_count"] == 10
        assert summary["average_cost_per_message"] == 0.005
