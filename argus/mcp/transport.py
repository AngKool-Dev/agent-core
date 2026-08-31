"""MCP transport layer for ARGUS."""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from argus.mcp.errors import (
    MCPConnectionError,
    MCPError,
    MCPProtocolError,
    MCPTimeoutError,
)


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class TransportConfig:
    """Configuration for MCP transport."""
    type: TransportType = TransportType.STDIO
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 3


@dataclass
class MCPMessage:
    """An MCP protocol message."""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error_data: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """Serialize to JSON-RPC message."""
        msg: Dict[str, Any] = {"jsonrpc": self.__dict__.get("jsonrpc", "2.0")}

        msg_id = self.__dict__.get("id")
        if msg_id is not None:
            msg["id"] = str(msg_id)

        method = self.__dict__.get("method", "")
        if method:
            msg["method"] = str(method)
            params = self.__dict__.get("params", {})
            msg["params"] = dict(params) if params else {}

        result = self.__dict__.get("result")
        if result is not None:
            msg["result"] = result

        error = self.__dict__.get("error_data")
        if error is not None:
            msg["error"] = error

        return json.dumps(msg)

    @classmethod
    def from_json(cls, data: str) -> "MCPMessage":
        """Deserialize from JSON-RPC message."""
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise MCPProtocolError(f"Invalid JSON in MCP message: {e}")

        if parsed.get("jsonrpc") != "2.0":
            raise MCPProtocolError("Invalid JSON-RPC version")

        return cls(
            jsonrpc=parsed.get("jsonrpc", "2.0"),
            id=parsed.get("id"),
            method=parsed.get("method", ""),
            params=parsed.get("params", {}),
            result=parsed.get("result"),
            error_data=parsed.get("error"),
        )

    @classmethod
    def request(cls, id: str, method: str, params: Dict[str, Any] = None) -> "MCPMessage":
        """Create a request message."""
        return cls(id=id, method=method, params=params or {})

    @classmethod
    def response(cls, id: str, result: Any) -> "MCPMessage":
        """Create a response message."""
        return cls(id=id, result=result)

    @classmethod
    def error(cls, id: str, code: int, message: str) -> "MCPMessage":
        """Create an error message."""
        return cls(id=id, error_data={"code": code, "message": message})

    @classmethod
    def notification(cls, method: str, params: Dict[str, Any] = None) -> "MCPMessage":
        """Create a notification message."""
        return cls(method=method, params=params or {})


class StdioTransport:
    """Stdio-based MCP transport."""

    def __init__(self, config: TransportConfig):
        self._config = config
        self._process: Optional[subprocess.Popen] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._request_id = 0
        self._connected = False
        self._buffer = ""
        self._notification_handlers: List[Callable[[MCPMessage], None]] = []

    @property
    def is_connected(self) -> bool:
        return self._connected and self._process is not None

    async def connect(self) -> None:
        """Connect to MCP server via stdio."""
        try:
            self._process = subprocess.Popen(
                [self._config.command] + self._config.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**self._config.env} if self._config.env else None,
                text=True,
                bufsize=1,
            )
            self._connected = True
        except Exception as e:
            raise MCPConnectionError(
                f"Failed to start MCP server: {e}",
                details=str(e),
            )

    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        self._connected = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None

        for future in self._pending.values():
            if not future.done():
                future.set_exception(MCPError("Transport disconnected"))
        self._pending.clear()

    async def send(self, message: MCPMessage) -> MCPMessage:
        """Send a message and wait for response."""
        if not self.is_connected:
            raise MCPConnectionError("Not connected to MCP server")

        if message.id is None:
            self._request_id += 1
            message.id = str(self._request_id)

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[message.id] = future

        try:
            line = message.to_json() + "\n"
            self._process.stdin.write(line)
            self._process.stdin.flush()

            response = await asyncio.wait_for(future, timeout=self._config.timeout)
            return response

        except asyncio.TimeoutError:
            self._pending.pop(message.id, None)
            raise MCPTimeoutError(
                f"MCP request timed out after {self._config.timeout}s",
            )
        except Exception as e:
            self._pending.pop(message.id, None)
            raise

    async def send_notification(self, message: MCPMessage) -> None:
        """Send a notification (no response expected)."""
        if not self.is_connected:
            raise MCPConnectionError("Not connected to MCP server")

        line = message.to_json() + "\n"
        self._process.stdin.write(line)
        self._process.stdin.flush()

    def add_notification_handler(self, handler: Callable[[MCPMessage], None]) -> None:
        """Add a notification handler."""
        self._notification_handlers.append(handler)

    async def read_responses(self) -> None:
        """Read responses from server (run as background task)."""
        while self.is_connected and self._process:
            try:
                line = self._process.stdout.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                message = MCPMessage.from_json(line)

                if message.id and message.id in self._pending:
                    future = self._pending.pop(message.id)
                    if not future.done():
                        future.set_result(message)
                elif message.method:
                    for handler in self._notification_handlers:
                        handler(message)

            except json.JSONDecodeError:
                continue
            except Exception:
                break

        self._connected = False


class SSETransport:
    """SSE-based MCP transport (placeholder for future implementation)."""

    def __init__(self, config: TransportConfig):
        self._config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to MCP server via SSE."""
        raise MCPError("SSE transport not yet implemented")

    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        self._connected = False

    async def send(self, message: MCPMessage) -> MCPMessage:
        """Send a message and wait for response."""
        raise MCPError("SSE transport not yet implemented")

    async def send_notification(self, message: MCPMessage) -> None:
        """Send a notification."""
        raise MCPError("SSE transport not yet implemented")


def create_transport(config: TransportConfig):
    """Create a transport based on configuration."""
    if config.type == TransportType.STDIO:
        return StdioTransport(config)
    elif config.type == TransportType.SSE:
        return SSETransport(config)
    else:
        raise MCPError(f"Unsupported transport type: {config.type}")
