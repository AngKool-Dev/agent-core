"""Argus Ollama provider."""

from typing import Any, Dict, List, Optional

from .provider import Message, ModelProvider, ModelResponse, ToolCall


class OllamaProvider(ModelProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url.rstrip("/")

    def complete(
        self,
        messages: List[Message],
        model: str = "llama3",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": kwargs.get("options", {}),
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
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=kwargs.get("timeout", 120),
        )
        response.raise_for_status()
        data = response.json()

        content = data.get("message", {}).get("content", "")
        tool_calls = []
        raw_tool_calls = data.get("message", {}).get("tool_calls")

        if raw_tool_calls:
            for tc in raw_tool_calls:
                tool_calls.append(ToolCall(
                    tool_name=tc.get("function", {}).get("name", ""),
                    arguments=tc.get("function", {}).get("arguments", {}),
                    call_id=tc.get("function", {}).get("name", ""),
                ))

        return ModelResponse(
            content=content,
            model=data.get("model", model),
            finish_reason=data.get("done_reason", "stop"),
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
        )

    def stream(self, messages: List[Message], model: str = "llama3", **kwargs):
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": kwargs.get("options", {}),
        }

        return requests.post(
            f"{self._base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=kwargs.get("timeout", 120),
        )
