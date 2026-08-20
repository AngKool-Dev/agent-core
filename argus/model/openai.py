"""Argus OpenAI provider."""

from typing import Any, Dict, List, Optional

from .provider import Message, ModelProvider, ModelResponse, ToolCall


class OpenAIProvider(ModelProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def complete(
        self,
        messages: List[Message],
        model: str = "gpt-4o",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package is not installed")

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)

        request_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        }

        if tools:
            request_kwargs["tools"] = [
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

        response = client.chat.completions.create(**request_kwargs)

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = []

        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(ToolCall(
                    tool_name=tc.function.name,
                    arguments=_safe_json_loads(tc.function.arguments),
                    call_id=tc.id,
                ))

        return ModelResponse(
            content=content,
            model=response.model,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
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


def _safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        import json
        return json.loads(text)
    except Exception:
        return {}
