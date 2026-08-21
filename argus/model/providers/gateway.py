"""Argus Free Gateway client and API contract."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..provider import Message, ModelProvider, ModelResponse, ToolCall


class GatewayError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, retry_after: Optional[float] = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class GatewayRateLimitError(GatewayError):
    pass


class GatewayUnavailableError(GatewayError):
    pass


class GatewayAuthError(GatewayError):
    pass


@dataclass
class GatewayModel:
    id: str
    provider: str
    free: bool
    tool_calling: bool = True
    streaming: bool = False
    context_window: int = 0
    capabilities: List[str] = field(default_factory=list)
    available: bool = True
    rate_limit: Optional[str] = None
    reset_info: Optional[str] = None


@dataclass
class GatewayHealth:
    status: str
    anonymous_available: bool
    providers: List[str]


class GatewayClient:
    DEFAULT_BASE_URL = "https://gateway.argus.ai/v1"
    DEFAULT_TIMEOUT = 120

    def __init__(self, base_url: str = "", api_key: str = "", timeout: int = DEFAULT_TIMEOUT):
        self._base_url = base_url.rstrip("/") or self.DEFAULT_BASE_URL
        self._api_key = api_key
        self._timeout = timeout

    def health(self) -> GatewayHealth:
        response = self._request("GET", "/health")
        data = response.json()
        return GatewayHealth(
            status=data.get("status", "unknown"),
            anonymous_available=data.get("anonymous_available", False),
            providers=data.get("providers", []),
        )

    def list_models(self) -> List[GatewayModel]:
        response = self._request("GET", "/models")
        data = response.json()
        models = []
        for m in data.get("data", []):
            models.append(GatewayModel(
                id=m.get("id", ""),
                provider=m.get("provider", ""),
                free=m.get("free", True),
                tool_calling=m.get("tool_calling", True),
                streaming=m.get("streaming", False),
                context_window=m.get("context_window", 0),
                capabilities=m.get("capabilities", []),
                available=m.get("available", True),
                rate_limit=m.get("rate_limit"),
                reset_info=m.get("reset_info"),
            ))
        return models

    def chat_completions(
        self,
        model: str,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
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

        response = self._request("POST", "/chat/completions", json=payload)
        return response.json()

    def _request(self, method: str, path: str, **kwargs):
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is not installed")

        url = f"{self._base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.setdefault("Content-Type", "application/json")
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        kwargs.setdefault("timeout", self._timeout)

        try:
            response = requests.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as e:
            raise GatewayUnavailableError(f"Gateway unreachable: {e}") from e

        if response.status_code == 429:
            retry_after = None
            if "Retry-After" in response.headers:
                try:
                    retry_after = float(response.headers["Retry-After"])
                except (ValueError, TypeError):
                    pass
            raise GatewayRateLimitError(
                f"Rate limited by gateway: {response.text}",
                status_code=response.status_code,
                retry_after=retry_after,
            )

        if response.status_code == 401:
            raise GatewayAuthError(f"Gateway auth failed: {response.text}", status_code=response.status_code)

        if response.status_code == 503:
            raise GatewayUnavailableError(
                f"Gateway unavailable: {response.text}", status_code=response.status_code
            )

        if not response.ok:
            raise GatewayError(f"Gateway error {response.status_code}: {response.text}", status_code=response.status_code)

        return response


class GatewayModelProvider(ModelProvider):
    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: int = GatewayClient.DEFAULT_TIMEOUT,
        fallback_provider: Optional[ModelProvider] = None,
    ):
        self._client = GatewayClient(base_url=base_url, api_key=api_key, timeout=timeout)
        self._fallback_provider = fallback_provider
        self._models: List[GatewayModel] = []

    def complete(
        self,
        messages: List[Message],
        model: str = "auto",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        try:
            return self._complete_via_gateway(messages, model, tools, **kwargs)
        except GatewayUnavailableError:
            if self._fallback_provider:
                return self._fallback_provider.complete(messages=messages, model=model, tools=tools, **kwargs)
            raise
        except GatewayRateLimitError:
            if self._fallback_provider:
                return self._fallback_provider.complete(messages=messages, model=model, tools=tools, **kwargs)
            raise

    def stream(self, messages: List[Message], model: str = "auto", **kwargs):
        try:
            return self._stream_via_gateway(messages, model, **kwargs)
        except GatewayUnavailableError:
            if self._fallback_provider:
                return self._fallback_provider.stream(messages=messages, model=model, **kwargs)
            raise
        except GatewayRateLimitError:
            if self._fallback_provider:
                return self._fallback_provider.stream(messages=messages, model=model, **kwargs)
            raise

    def _complete_via_gateway(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict[str, Any]]],
        **kwargs,
    ) -> ModelResponse:
        data = self._client.chat_completions(
            model=model,
            messages=messages,
            tools=tools,
            stream=False,
            **kwargs,
        )

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

    def _stream_via_gateway(self, messages: List[Message], model: str, **kwargs):
        data = self._client.chat_completions(
            model=model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        return data

    def health(self) -> GatewayHealth:
        return self._client.health()

    def list_models(self) -> List[GatewayModel]:
        return self._client.list_models()
