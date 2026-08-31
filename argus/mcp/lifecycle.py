"""MCP lifecycle management for ARGUS."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from argus.mcp.adapter import MCPPromptAdapter, MCPResourceAdapter, create_mcp_capability
from argus.mcp.client import MCPClient
from argus.mcp.errors import MCPConnectionError, MCPError, MCPTimeoutError
from argus.mcp.registry import MCPRegistry, ServerStatus
from argus.mcp.transport import TransportConfig, create_transport


class LifecycleEvent(str, Enum):
    SERVER_REGISTERED = "server_registered"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    CAPABILITY_DISCOVERED = "capability_discovered"
    READY = "ready"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    FAILED = "failed"


@dataclass
class LifecycleEventData:
    """Data associated with a lifecycle event."""
    event: LifecycleEvent
    server_id: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)


class MCPLifecycleManager:
    """Manages the lifecycle of MCP servers."""

    def __init__(self, registry: MCPRegistry):
        self._registry = registry
        self._event_handlers: List[Callable[[LifecycleEventData], None]] = []
        self._health_check_interval: float = 30.0
        self._auto_reconnect: bool = True
        self._max_reconnect_attempts: int = 3
        self._reconnect_delay: float = 5.0

    @property
    def registry(self) -> MCPRegistry:
        return self._registry

    def add_event_handler(self, handler: Callable[[LifecycleEventData], None]) -> None:
        """Add a lifecycle event handler."""
        self._event_handlers.append(handler)

    def remove_event_handler(self, handler: Callable[[LifecycleEventData], None]) -> None:
        """Remove a lifecycle event handler."""
        self._event_handlers.remove(handler)

    def _emit_event(self, event: LifecycleEvent, server_id: str, details: Dict[str, Any] = None) -> None:
        """Emit a lifecycle event."""
        data = LifecycleEventData(
            event=event,
            server_id=server_id,
            details=details or {},
        )
        for handler in self._event_handlers:
            handler(data)

    async def start_server(
        self,
        server_id: str,
        config: TransportConfig,
        discover_capabilities: bool = True,
    ) -> bool:
        """Start an MCP server and optionally discover capabilities."""
        self._registry.register_server(server_id, config)
        self._emit_event(LifecycleEvent.SERVER_REGISTERED, server_id)

        self._registry.update_server_status(server_id, ServerStatus.CONNECTING)
        self._emit_event(LifecycleEvent.CONNECTING, server_id)

        try:
            client = MCPClient(server_id, config)
            await client.connect()

            self._registry.update_server_status(server_id, ServerStatus.CONNECTED)
            self._emit_event(LifecycleEvent.CONNECTED, server_id)

            self._registry.update_server_status(server_id, ServerStatus.INITIALIZING)
            self._emit_event(LifecycleEvent.INITIALIZING, server_id)

            server_info = await client.initialize()

            self._emit_event(LifecycleEvent.INITIALIZED, server_id, {
                "server_name": server_info.name,
                "server_version": server_info.version,
            })

            entry = self._registry.get_server(server_id)
            if entry:
                entry.client = client

            if discover_capabilities:
                await self._discover_capabilities(server_id, client)

            self._registry.update_server_status(server_id, ServerStatus.READY)
            self._emit_event(LifecycleEvent.READY, server_id)

            return True

        except MCPTimeoutError as e:
            self._registry.update_server_status(server_id, ServerStatus.ERROR, str(e))
            self._emit_event(LifecycleEvent.ERROR, server_id, {"error": str(e)})
            return False

        except MCPConnectionError as e:
            self._registry.update_server_status(server_id, ServerStatus.ERROR, str(e))
            self._emit_event(LifecycleEvent.FAILED, server_id, {"error": str(e)})
            return False

        except Exception as e:
            self._registry.update_server_status(server_id, ServerStatus.ERROR, str(e))
            self._emit_event(LifecycleEvent.ERROR, server_id, {"error": str(e)})
            return False

    async def stop_server(self, server_id: str) -> bool:
        """Stop an MCP server."""
        entry = self._registry.get_server(server_id)
        if not entry:
            return False

        self._emit_event(LifecycleEvent.DISCONNECTING, server_id)

        if entry.client and entry.client.is_connected:
            try:
                await entry.client.disconnect()
            except Exception:
                pass

        self._registry.update_server_status(server_id, ServerStatus.DISCONNECTED)
        self._emit_event(LifecycleEvent.DISCONNECTED, server_id)

        return True

    async def restart_server(self, server_id: str) -> bool:
        """Restart an MCP server."""
        entry = self._registry.get_server(server_id)
        if not entry:
            return False

        await self.stop_server(server_id)
        return await self.start_server(server_id, entry.config)

    async def _discover_capabilities(self, server_id: str, client: MCPClient) -> None:
        """Discover capabilities from an MCP server."""
        try:
            tools = await client.list_tools()
            for tool_def in tools:
                capability = create_mcp_capability(tool_def, client)
                self._registry.register_capability(server_id, capability)
                self._emit_event(LifecycleEvent.CAPABILITY_DISCOVERED, server_id, {
                    "capability_id": capability.metadata.id,
                    "tool_name": tool_def.name,
                })
        except MCPError:
            pass

        try:
            resources = await client.list_resources()
            for res_def in resources:
                resource = MCPResourceAdapter(res_def, client)
                self._registry.register_resource(server_id, resource)
        except MCPError:
            pass

        try:
            prompts = await client.list_prompts()
            for prompt_def in prompts:
                prompt = MCPPromptAdapter(prompt_def, client)
                self._registry.register_prompt(server_id, prompt)
        except MCPError:
            pass

    async def health_check(self, server_id: str) -> Dict[str, Any]:
        """Perform health check on a server."""
        entry = self._registry.get_server(server_id)
        if not entry or not entry.client:
            return {"status": "not_found"}

        if not entry.client.is_connected:
            return {"status": "disconnected"}

        try:
            tools = await entry.client.list_tools()
            return {
                "status": "healthy",
                "tool_count": len(tools),
                "last_activity": entry.client.state.last_activity,
            }
        except MCPTimeoutError:
            return {"status": "timeout"}
        except MCPError as e:
            return {"status": "error", "error": str(e)}

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health check on all servers."""
        results = {}
        for server_id in self._registry._servers:
            results[server_id] = await self.health_check(server_id)
        return results

    async def start_all(self, configs: Dict[str, TransportConfig]) -> Dict[str, bool]:
        """Start all configured servers."""
        results = {}
        for server_id, config in configs.items():
            results[server_id] = await self.start_server(server_id, config)
        return results

    async def stop_all(self) -> None:
        """Stop all running servers."""
        for server_id in list(self._registry._servers.keys()):
            await self.stop_server(server_id)

    def get_server_info(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get server information."""
        entry = self._registry.get_server(server_id)
        if not entry:
            return None

        return {
            "server_id": entry.server_id,
            "status": entry.status.value,
            "capability_count": len(entry.capabilities),
            "resource_count": len(entry.resources),
            "prompt_count": len(entry.prompts),
            "error_message": entry.error_message,
            "registered_at": entry.registered_at,
            "last_connected": entry.last_connected,
            "last_error": entry.last_error,
        }

    def get_all_server_info(self) -> List[Dict[str, Any]]:
        """Get information for all servers."""
        return [
            self.get_server_info(server_id)
            for server_id in self._registry._servers
        ]
