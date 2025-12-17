"""Pytest configuration and shared fixtures."""

import os
import pytest
import asyncio
from typing import AsyncGenerator

# Set test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_assistant"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # Use DB 1 for tests
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_anthropic_key():
    """Mock Anthropic API key."""
    return "sk-ant-test-key"


@pytest.fixture
def mock_openai_key():
    """Mock OpenAI API key."""
    return "sk-test-key"


@pytest.fixture
def mock_google_key():
    """Mock Google API key."""
    return "AI-test-key"


@pytest.fixture
async def anthropic_provider(mock_anthropic_key):
    """Create mock Anthropic provider."""
    from providers.anthropic_provider import AnthropicProvider
    from providers.base import ProviderConfig

    config = ProviderConfig(api_key=mock_anthropic_key)
    provider = AnthropicProvider(config)
    # Don't actually initialize in tests
    yield provider


@pytest.fixture
async def openai_provider(mock_openai_key):
    """Create mock OpenAI provider."""
    from providers.openai_provider import OpenAIProvider
    from providers.base import ProviderConfig

    config = ProviderConfig(api_key=mock_openai_key)
    provider = OpenAIProvider(config)
    yield provider


@pytest.fixture
async def google_provider(mock_google_key):
    """Create mock Google provider."""
    from providers.google_provider import GoogleProvider
    from providers.base import ProviderConfig

    config = ProviderConfig(api_key=mock_google_key)
    provider = GoogleProvider(config)
    yield provider


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    from providers.base import Message

    return [
        Message(role="user", content="Hello, how are you?"),
    ]


@pytest.fixture
def sample_vision_image_path(tmp_path):
    """Create a sample image for vision tests."""
    from PIL import Image

    img = Image.new('RGB', (100, 100), color='white')
    img_path = tmp_path / "test_image.png"
    img.save(img_path)
    return str(img_path)


@pytest.fixture
async def chat_router(anthropic_provider, google_provider):
    """Create chat router with mock providers."""
    from services.chat import ChatRouter

    router = ChatRouter(
        primary=anthropic_provider,
        fallback=google_provider,
        strategy="capability_based"
    )
    yield router
    await router.close()


@pytest.fixture
def cost_tracker():
    """Create cost tracker for testing."""
    from observability.costs import CostTracker

    tracker = CostTracker()
    yield tracker
