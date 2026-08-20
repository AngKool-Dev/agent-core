"""Argus Ollama provider."""

from typing import List, Optional

from .provider import Message, ModelProvider, ModelResponse


class OllamaProvider(ModelProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url.rstrip("/")

    def complete(self, messages: List[Message], model: str = "llama3", **kwargs) -> ModelResponse:
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        response = requests.post(
            f"{self._base_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                **kwargs,
            },
        )
        response.raise_for_status()
        data = response.json()

        return ModelResponse(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", model),
            usage=data.get("usage", {}),
        )

    def stream(self, messages: List[Message], model: str = "llama3", **kwargs):
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        return requests.post(
            f"{self._base_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": True,
                **kwargs,
            },
            stream=True,
        )
