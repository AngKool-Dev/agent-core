"""Argus model factory."""

from typing import Optional

from .anthropic import AnthropicProvider
from .openai import OpenAIProvider
from .ollama import OllamaProvider
from .provider import ModelProvider


def create_provider(provider_type: str, **kwargs) -> ModelProvider:
    provider_type = provider_type.lower()
    if provider_type == "openai":
        return OpenAIProvider(**kwargs)
    elif provider_type == "anthropic":
        return AnthropicProvider(**kwargs)
    elif provider_type == "ollama":
        return OllamaProvider(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider_type}")
