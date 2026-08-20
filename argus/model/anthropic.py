"""Argus Anthropic provider."""

from typing import Any, Dict, List, Optional

from .provider import Message, ModelProvider, ModelResponse, ToolCall


class AnthropicProvider(ModelProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def complete(
        self,
        messages: List[Message],
        model: str = "claude-sonnet-4-20250514",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
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

        request_kwargs: Dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": chat_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        if tools:
            request_kwargs["tools"] = [
                {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
            ]

        response = client.messages.create(**request_kwargs)

        content = ""
        tool_calls = []
        reasoning = None

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    tool_name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                    call_id=block.id,
                ))
            elif block.type == "thinking":
                reasoning = block.text

        return ModelResponse(
            content=content,
            model=response.model,
            finish_reason=response.stop_reason,
            tool_calls=tool_calls,
            reasoning=reasoning,
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
            **kwargs,
        )
