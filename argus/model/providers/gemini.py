"""Argus Gemini provider."""

from typing import Any, Dict, List, Optional

from ..provider import Message, ModelProvider, ModelResponse, ToolCall


GEMINI_FREE_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


class GeminiProvider(ModelProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def complete(
        self,
        messages: List[Message],
        model: str = "gemini-2.0-flash",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self._api_key}"

        system_parts = []
        contents = []
        for m in messages:
            if m.role == "system":
                system_parts.append({"text": m.content})
            else:
                role = "user" if m.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.content}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": kwargs.get("temperature", 0.7)},
        }

        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        if tools:
            function_declarations = []
            for t in tools:
                function_declarations.append({
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                })
            payload["tools"] = [{"functionDeclarations": function_declarations}]

        response = requests.post(url, json=payload, timeout=kwargs.get("timeout", 120))
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        content = ""
        tool_calls = []
        reasoning = None

        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    content += part["text"]
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append(ToolCall(
                        tool_name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                        call_id=fc.get("name", ""),
                    ))
                elif "thought" in part:
                    reasoning = part["thought"]

        return ModelResponse(
            content=content,
            model=model,
            finish_reason="stop",
            tool_calls=tool_calls,
            reasoning=reasoning,
            usage=data.get("usageMetadata", {}),
        )

    def stream(self, messages: List[Message], model: str = "gemini-2.0-flash", **kwargs):
        raise NotImplementedError("Gemini streaming not yet implemented")
