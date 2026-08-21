"""Argus Free Gateway server."""

import json
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..model import create_router_from_config
from ..model.provider import Message, ModelResponse
from ..model.usage import UsageTracker


class GatewayRateLimitError(Exception):
    def __init__(self, retry_after: float):
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


class GatewayNoProviderError(Exception):
    pass


@dataclass
class RateLimiter:
    max_requests: int = 20
    window_seconds: float = 3600.0

    def __init__(self, max_requests: int = 20, window_seconds: float = 3600.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, List[float]] = {}

    def allow(self, client_id: str) -> Tuple[bool, Optional[float]]:
        now = time.time()
        window_start = now - self.window_seconds
        timestamps = self._buckets.get(client_id, [])
        timestamps = [t for t in timestamps if t > window_start]
        timestamps.append(now)
        self._buckets[client_id] = timestamps

        if len(timestamps) > self.max_requests:
            retry_after = timestamps[0] + self.window_seconds - now
            return False, max(retry_after, 1.0)
        return True, None

    def reset(self, client_id: str) -> None:
        self._buckets.pop(client_id, None)


@dataclass
class GatewayServerConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    free_requests: int = 20
    free_window_seconds: float = 3600.0
    providers: Dict[str, Any] = field(default_factory=dict)
    strategy: str = "free_first"
    max_retries: int = 3


def _normalize_providers(providers: Any) -> Dict[str, Any]:
    if isinstance(providers, dict):
        return providers
    if isinstance(providers, list):
        return {p["name"]: p for p in providers if isinstance(p, dict) and "name" in p}
    return {}


class GatewayServer:
    MAX_RETRIES = 3

    def __init__(self, config: Optional[GatewayServerConfig] = None):
        self.config = config or GatewayServerConfig()
        self._rate_limiter = RateLimiter(
            max_requests=self.config.free_requests,
            window_seconds=self.config.free_window_seconds,
        )
        self._usage = UsageTracker()
        self._router = self._build_router()

    def _build_router(self):
        providers = _normalize_providers(self.config.providers)
        hub_config = {
            "strategy": self.config.strategy or "free_first",
            "budget": {"allow_paid": False, "daily_limit": 0.0},
            "providers": providers,
        }
        try:
            return create_router_from_config(hub_config, usage_tracker=self._usage)
        except Exception:
            return None

    def _is_retryable_error(self, error: Exception) -> bool:
        error_str = str(error).lower()
        if "auth" in error_str or "unauthorized" in error_str or "401" in error_str:
            return False
        if "invalid" in error_str and "request" in error_str:
            return False
        return True

    def _extract_request_text(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        for message in reversed(messages):
            if message.get("role") == "user" and message.get("content"):
                return message["content"]
        return None

    def create_handler(self) -> type:
        server = self

        class GatewayRequestHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def _send_json(self, status: int, data: Dict[str, Any]) -> None:
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_sse(self, body: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))

            def _client_id(self) -> str:
                forwarded = self.headers.get("X-Forwarded-For", "")
                if forwarded:
                    return forwarded.split(",")[0].strip()
                return self.client_address[0]

            def _handle_health(self) -> None:
                anonymous_available = False
                free_model_count = 0
                providers: List[str] = []

                if server._router:
                    for state in server._router._registry.list_states():
                        cap = state.capability
                        if cap.free and cap.available:
                            anonymous_available = True
                            free_model_count += len(cap.models)
                            providers.append(cap.name)

                self._send_json(200, {
                    "status": "ok",
                    "anonymous_available": anonymous_available,
                    "providers": providers,
                    "free_model_count": free_model_count,
                })

            def _handle_models(self) -> None:
                models = []
                if server._router:
                    seen = set()
                    for state in server._router._registry.list_states():
                        cap = state.capability
                        if not cap.free:
                            continue
                        if not cap.available:
                            continue
                        for model_id in cap.models:
                            if model_id in seen:
                                continue
                            seen.add(model_id)
                            models.append({
                                "id": model_id,
                                "provider": cap.name,
                                "free": True,
                                "tool_calling": cap.tool_calling,
                                "streaming": cap.streaming,
                                "context_window": cap.context_window,
                                "capabilities": cap.capabilities,
                                "available": cap.available,
                                "priority": cap.priority,
                            })

                self._send_json(200, {"data": models})

            def _handle_chat_completions(self) -> None:
                client_id = self._client_id()
                allowed, retry_after = server._rate_limiter.allow(client_id)
                if not allowed:
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Retry-After", str(int(retry_after)))
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Rate limit exceeded", "retry_after": retry_after}).encode("utf-8"))
                    return

                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)

                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "Invalid JSON"})
                    return

                model = payload.get("model", "auto")
                messages = payload.get("messages", [])
                tools = payload.get("tools")
                stream = bool(payload.get("stream", False))

                if not messages:
                    self._send_json(400, {"error": "Missing messages"})
                    return

                if not server._router:
                    self._send_json(503, {"error": "No free provider available"})
                    return

                if model != "auto":
                    is_free = False
                    for state in server._router._registry.list_states():
                        if model in state.capability.models and state.capability.free:
                            is_free = True
                            break
                    if not is_free:
                        self._send_json(403, {"error": "Paid models are not available for anonymous requests"})
                        return

                try:
                    if stream:
                        self._handle_stream(model, messages, tools, payload)
                    else:
                        self._handle_completion(model, messages, tools, payload)
                except GatewayNoProviderError:
                    self._send_json(503, {"error": "No free provider available"})
                except Exception as exc:
                    self._send_json(502, {"error": "Provider error"})

            def _handle_completion(self, model: str, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], payload: Dict[str, Any]) -> None:
                request_text = server._extract_request_text(messages)
                last_exception = None

                for attempt in range(server.config.max_retries):
                    try:
                        response = server._router.complete(
                            messages=[Message(role=m.get("role", "user"), content=m.get("content", "")) for m in messages],
                            model=model,
                            tools=tools,
                            request=request_text,
                            temperature=payload.get("temperature"),
                            max_tokens=payload.get("max_tokens") or payload.get("max_completion_tokens"),
                        )
                        choice = {
                            "message": {
                                "role": "assistant",
                                "content": response.content,
                            },
                            "finish_reason": response.finish_reason,
                        }

                        if response.tool_calls:
                            choice["message"]["tool_calls"] = [
                                {
                                    "id": tc.call_id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.tool_name,
                                        "arguments": tc.arguments,
                                    },
                                }
                                for tc in response.tool_calls
                            ]

                        data = {
                            "model": response.model,
                            "choices": [choice],
                            "usage": response.usage or {},
                        }
                        self._send_json(200, data)
                        return
                    except RuntimeError:
                        raise GatewayNoProviderError()
                    except Exception as e:
                        last_exception = e
                        if not server._is_retryable_error(e):
                            break

                if isinstance(last_exception, RuntimeError):
                    raise GatewayNoProviderError()
                raise last_exception or RuntimeError("No available model provider")

            def _handle_stream(self, model: str, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], payload: Dict[str, Any]) -> None:
                request_text = server._extract_request_text(messages)
                last_exception = None

                for attempt in range(server.config.max_retries):
                    try:
                        stream = server._router.stream(
                            messages=[Message(role=m.get("role", "user"), content=m.get("content", "")) for m in messages],
                            model=model,
                            tools=tools,
                            request=request_text,
                            temperature=payload.get("temperature"),
                            max_tokens=payload.get("max_tokens") or payload.get("max_completion_tokens"),
                        )
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "keep-alive")
                        self.end_headers()

                        try:
                            for chunk in stream:
                                if hasattr(chunk, "content"):
                                    data = json.dumps({"choices": [{"delta": {"content": chunk.content}}]})
                                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                                    self.wfile.flush()
                                elif isinstance(chunk, dict):
                                    data = json.dumps(chunk)
                                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                                    self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            pass

                        try:
                            self.wfile.write(b"data: [DONE]\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                        return
                    except RuntimeError:
                        raise GatewayNoProviderError()
                    except Exception as e:
                        last_exception = e
                        if not server._is_retryable_error(e):
                            break

                if isinstance(last_exception, RuntimeError):
                    raise GatewayNoProviderError()
                raise last_exception or RuntimeError("No available model provider")

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/health":
                    self._handle_health()
                elif path == "/v1/models":
                    self._handle_models()
                else:
                    self._send_json(404, {"error": "Not found"})

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/v1/chat/completions":
                    self._handle_chat_completions()
                else:
                    self._send_json(404, {"error": "Not found"})

        return GatewayRequestHandler

    def serve(self) -> None:
        handler = self.create_handler()
        httpd = ThreadingHTTPServer((self.config.host, self.config.port), handler)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
