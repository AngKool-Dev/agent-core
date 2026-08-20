"""Argus model package."""

from .factory import create_model_from_config, create_provider, create_router_from_config
from .messages import build_messages, parse_model_output
from .provider import Message, ModelProvider, ModelResponse, ToolCall
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider
from .ollama import OllamaProvider
from .providers.gemini import GeminiProvider
from .providers.openrouter import OpenRouterProvider
from .providers.groq import GroqProvider
from .providers.cerebras import CerebrasProvider
from .hub import Budget, ModelRouter, ProviderCapability, ProviderRegistry, ProviderState, Strategy, TaskClassifier
from .credentials import CredentialManager
from .usage import UsageEntry, UsageTracker

__all__ = [
    "Message",
    "ModelResponse",
    "ToolCall",
    "ModelProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "GeminiProvider",
    "OpenRouterProvider",
    "GroqProvider",
    "CerebrasProvider",
    "create_provider",
    "create_model_from_config",
    "create_router_from_config",
    "build_messages",
    "parse_model_output",
    "Budget",
    "ModelRouter",
    "ProviderCapability",
    "ProviderRegistry",
    "ProviderState",
    "Strategy",
    "TaskClassifier",
    "CredentialManager",
    "UsageEntry",
    "UsageTracker",
]
