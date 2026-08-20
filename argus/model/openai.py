"""Argus OpenAI provider."""

from typing import List, Optional

from .provider import Message, ModelProvider, ModelResponse


class OpenAIProvider(ModelProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def complete(self, messages: List[Message], model: str = "gpt-4o", **kwargs) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package is not installed")

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        )

        return ModelResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        )

    def stream(self, messages: List[Message], model: str = "gpt-4o", **kwargs):
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package is not installed")

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            stream=True,
            **kwargs,
        )
