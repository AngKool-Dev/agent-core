"""Argus Anthropic provider."""

from typing import List, Optional

from .provider import Message, ModelProvider, ModelResponse


class AnthropicProvider(ModelProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def complete(self, messages: List[Message], model: str = "claude-sonnet-4-20250514", **kwargs) -> ModelResponse:
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("anthropic package is not installed")

        client = Anthropic(api_key=self._api_key)
        system = None
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        response = client.messages.create(
            model=model,
            system=system,
            messages=chat_messages,
            max_tokens=kwargs.get("max_tokens", 4096),
        )

        return ModelResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    def stream(self, messages: List[Message], model: str = "claude-sonnet-4-20250514", **kwargs):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("anthropic package is not installed")

        client = Anthropic(api_key=self._api_key)
        system = None
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        return client.messages.create(
            model=model,
            system=system,
            messages=chat_messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            stream=True,
        )
