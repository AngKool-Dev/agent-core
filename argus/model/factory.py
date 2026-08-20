"""Argus model factory."""

from typing import Any, Dict, Optional

from .anthropic import AnthropicProvider
from .hub import Budget, ModelRouter, ProviderCapability, ProviderRegistry, ProviderState, Strategy
from .openai import OpenAIProvider
from .ollama import OllamaProvider
from .provider import ModelProvider
from .providers.cerebras import CerebrasProvider
from .providers.gemini import GeminiProvider
from .providers.groq import GroqProvider
from .providers.openrouter import OpenRouterProvider


def create_provider(provider_type: str, **kwargs) -> ModelProvider:
    provider_type = provider_type.lower()
    if provider_type == "openai":
        return OpenAIProvider(**kwargs)
    elif provider_type == "anthropic":
        return AnthropicProvider(**kwargs)
    elif provider_type == "ollama":
        return OllamaProvider(**kwargs)
    elif provider_type == "openrouter":
        return OpenRouterProvider(**kwargs)
    elif provider_type == "gemini":
        return GeminiProvider(**kwargs)
    elif provider_type == "groq":
        return GroqProvider(**kwargs)
    elif provider_type == "cerebras":
        return CerebrasProvider(**kwargs)
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
    elif provider_type == "openrouter":
        kwargs["api_key"] = config.get("api_key", "")
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]
    elif provider_type == "gemini":
        kwargs["api_key"] = config.get("api_key", "")
    elif provider_type == "groq":
        kwargs["api_key"] = config.get("api_key", "")
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]
    elif provider_type == "cerebras":
        kwargs["api_key"] = config.get("api_key", "")
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]

    return create_provider(provider_type, **kwargs)


def create_router_from_config(config: Dict[str, Any]) -> ModelRouter:
    registry = ProviderRegistry()

    providers_config = config.get("providers", {})
    for name, pconfig in providers_config.items():
        if not pconfig.get("enabled", True):
            continue

        api_key = pconfig.get("api_key", "")
        base_url = pconfig.get("base_url", "")
        provider_kwargs: Dict[str, Any] = {}
        if api_key:
            provider_kwargs["api_key"] = api_key
        if base_url:
            provider_kwargs["base_url"] = base_url

        try:
            provider = create_provider(name, **provider_kwargs)
        except Exception:
            continue

        capability = ProviderCapability(
            name=name,
            models=pconfig.get("models", []),
            free=pconfig.get("free", True),
            tool_calling=pconfig.get("tool_calling", True),
            streaming=pconfig.get("streaming", False),
            context_window=pconfig.get("context_window", 0),
            capabilities=pconfig.get("capabilities", []),
            available=pconfig.get("available", True),
            rate_limit=pconfig.get("rate_limit"),
            reset_info=pconfig.get("reset_info"),
        )

        registry.register(ProviderState(capability=capability, provider=provider))

    strategy = Strategy(config.get("strategy", "free_first"))
    budget_config = config.get("budget", {})
    budget = Budget(
        allow_paid=budget_config.get("allow_paid", True),
        daily_limit=budget_config.get("daily_limit", 0.0),
    )

    preferred_model = config.get("preferred_model")
    return ModelRouter(registry=registry, strategy=strategy, budget=budget, preferred_model=preferred_model)
