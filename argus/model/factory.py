"""Argus model factory."""

from typing import Any, Dict, Optional

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


def create_model_from_config(config: Dict[str, Any]) -> ModelProvider:
    provider_type = config.get("provider", "ollama")
    kwargs: Dict[str, Any] = {}

    if provider_type == "openai":
        kwargs["api_key"] = config.get("api_key", "")
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]
    elif provider_type == "anthropic":
        kwargs["api_key"] = config.get("api_key", "")
    elif provider_type == "ollama":
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]

    return create_provider(provider_type, **kwargs)
