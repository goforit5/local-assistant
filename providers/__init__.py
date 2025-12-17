"""Provider wrappers for AI APIs."""

from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .base import BaseProvider, Message, CompletionResponse, ProviderConfig
from .factory import ProviderFactory, register_provider, ProviderRegistry

# Optional Google provider - only import if dependency is available
try:
    from .google_provider import GoogleProvider
    __all__ = [
        "AnthropicProvider",
        "OpenAIProvider",
        "GoogleProvider",
        "BaseProvider",
        "Message",
        "CompletionResponse",
        "ProviderConfig",
        "ProviderFactory",
        "register_provider",
        "ProviderRegistry",
    ]
except ImportError:
    __all__ = [
        "AnthropicProvider",
        "OpenAIProvider",
        "BaseProvider",
        "Message",
        "CompletionResponse",
        "ProviderConfig",
        "ProviderFactory",
        "register_provider",
        "ProviderRegistry",
    ]
