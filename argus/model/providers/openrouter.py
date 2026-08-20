"""Argus OpenRouter provider."""

from typing import Any, Dict, List, Optional

from ..provider import Message, ModelProvider, ModelResponse, ToolCall


OPENROUTER_FREE_MODELS = [
    "mistralai/mistral-7b-instruct",
    "google/gemma-2-9b-it",
    "meta-llama/llama-3.1-8b-instruct",
    "huggingfaceh4/zephyr-7b-beta",
    "nousresearch/nous-hermes-2-mixtral",
]


class OpenRouterProvider(ModelProvider):
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def complete(
        self,
        messages: List[Message],
        model: str = "mistralai/mistral-7b-instruct",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/argus-agent",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
                for t in tools
            ]

        response = requests.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=kwargs.get("timeout", 120),
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        content = choice["message"].get("content", "")
        tool_calls = []

        if choice["message"].get("tool_calls"):
            for tc in choice["message"]["tool_calls"]:
                tool_calls.append(ToolCall(
                    tool_name=tc.get("function", {}).get("name", ""),
                    arguments=tc.get("function", {}).get("arguments", {}),
                    call_id=tc.get("id", ""),
                ))

        return ModelResponse(
            content=content,
            model=data.get("model", model),
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
        )

    def stream(self, messages: List[Message], model: str = "mistralai/mistral-7b-instruct", **kwargs):
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/argus-agent",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }

        return requests.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=kwargs.get("timeout", 120),
        )
