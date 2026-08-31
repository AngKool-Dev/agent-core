"""MCP registry for ARGUS."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from argus.mcp.adapter import MCPPromptAdapter, MCPResourceAdapter, MCPCapabilityAdapter, create_mcp_capability
from argus.mcp.client import MCPClient
from argus.mcp.errors import MCPError
from argus.mcp.schemas import MCPPromptDefinition, MCPResourceDefinition, MCPToolDefinition
from argus.mcp.transport import TransportConfig


class ServerStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class MCPServerEntry:
    """Entry for a registered MCP server."""
    server_id: str
    config: TransportConfig
    status: ServerStatus = ServerStatus.DISCONNECTED
    client: Optional[MCPClient] = None
    capabilities: Dict[str, MCPCapabilityAdapter] = field(default_factory=dict)
    resources: Dict[str, MCPResourceAdapter] = field(default_factory=dict)
    prompts: Dict[str, MCPPromptAdapter] = field(default_factory=dict)
    error_message: str = ""
    registered_at: float = field(default_factory=time.time)
    last_connected: float = 0.0
    last_error: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPRegistry:
    """Registry for MCP servers and their capabilities."""

    def __init__(self):
        self._servers: Dict[str, MCPServerEntry] = {}
        self._capabilities: Dict[str, MCPCapabilityAdapter] = {}
        self._resources: Dict[str, MCPResourceAdapter] = {}
        self._prompts: Dict[str, MCPPromptAdapter] = {}

    @property
    def server_count(self) -> int:
        return len(self._servers)

    @property
    def capability_count(self) -> int:
        return len(self._capabilities)

    def register_server(
        self,
        server_id: str,
        config: TransportConfig,
        metadata: Dict[str, Any] = None,
    ) -> MCPServerEntry:
        """Register an MCP server."""
        if server_id in self._servers:
            raise MCPError(f"Server already registered: {server_id}")

        entry = MCPServerEntry(
            server_id=server_id,
            config=config,
            metadata=metadata or {},
        )
        self._servers[server_id] = entry
        return entry

    def unregister_server(self, server_id: str) -> bool:
        """Unregister an MCP server."""
        if server_id not in self._servers:
            return False

        entry = self._servers[server_id]

        for cap_id in list(entry.capabilities.keys()):
            self._capabilities.pop(cap_id, None)

        for res_uri in list(entry.resources.keys()):
            self._resources.pop(res_uri, None)

        for prompt_name in list(entry.prompts.keys()):
            self._prompts.pop(prompt_name, None)

        del self._servers[server_id]
        return True

    def get_server(self, server_id: str) -> Optional[MCPServerEntry]:
        """Get a server entry by ID."""
        return self._servers.get(server_id)

    def get_all_servers(self) -> List[MCPServerEntry]:
        """Get all server entries."""
        return list(self._servers.values())

    def get_servers_by_status(self, status: ServerStatus) -> List[MCPServerEntry]:
        """Get servers by status."""
        return [s for s in self._servers.values() if s.status == status]

    def update_server_status(
        self,
        server_id: str,
        status: ServerStatus,
        error_message: str = "",
    ) -> None:
        """Update server status."""
        if server_id in self._servers:
            entry = self._servers[server_id]
            entry.status = status
            if error_message:
                entry.error_message = error_message
                entry.last_error = time.time()
            if status == ServerStatus.READY:
                entry.last_connected = time.time()

    def register_capability(
        self,
        server_id: str,
        capability: MCPCapabilityAdapter,
    ) -> None:
        """Register a capability from an MCP server."""
        if server_id not in self._servers:
            raise MCPError(f"Server not registered: {server_id}")

        self._servers[server_id].capabilities[capability.metadata.id] = capability
        self._capabilities[capability.metadata.id] = capability

    def unregister_capability(self, capability_id: str) -> bool:
        """Unregister a capability."""
        if capability_id not in self._capabilities:
            return False

        capability = self._capabilities.pop(capability_id)

        for entry in self._servers.values():
            if capability_id in entry.capabilities:
                del entry.capabilities[capability_id]
                break

        return True

    def get_capability(self, capability_id: str) -> Optional[MCPCapabilityAdapter]:
        """Get a capability by ID."""
        return self._capabilities.get(capability_id)

    def get_all_capabilities(self) -> List[MCPCapabilityAdapter]:
        """Get all registered capabilities."""
        return list(self._capabilities.values())

    def get_capabilities_by_server(self, server_id: str) -> List[MCPCapabilityAdapter]:
        """Get capabilities for a specific server."""
        if server_id not in self._servers:
            return []
        return list(self._servers[server_id].capabilities.values())

    def get_capabilities_by_tag(self, tag: str) -> List[MCPCapabilityAdapter]:
        """Get capabilities by tag."""
        return [
            cap for cap in self._capabilities.values()
            if tag in cap.metadata.tags
        ]

    def register_resource(
        self,
        server_id: str,
        resource: MCPResourceAdapter,
    ) -> None:
        """Register a resource from an MCP server."""
        if server_id not in self._servers:
            raise MCPError(f"Server not registered: {server_id}")

        self._servers[server_id].resources[resource.uri] = resource
        self._resources[resource.uri] = resource

    def get_resource(self, uri: str) -> Optional[MCPResourceAdapter]:
        """Get a resource by URI."""
        return self._resources.get(uri)

    def get_all_resources(self) -> List[MCPResourceAdapter]:
        """Get all registered resources."""
        return list(self._resources.values())

    def register_prompt(
        self,
        server_id: str,
        prompt: MCPPromptAdapter,
    ) -> None:
        """Register a prompt from an MCP server."""
        if server_id not in self._servers:
            raise MCPError(f"Server not registered: {server_id}")

        self._servers[server_id].prompts[prompt.name] = prompt
        self._prompts[prompt.name] = prompt

    def get_prompt(self, name: str) -> Optional[MCPPromptAdapter]:
        """Get a prompt by name."""
        return self._prompts.get(name)

    def get_all_prompts(self) -> List[MCPPromptAdapter]:
        """Get all registered prompts."""
        return list(self._prompts.values())

    def discover_capabilities(self, server_id: str) -> Dict[str, Any]:
        """Discover capabilities from a connected server."""
        if server_id not in self._servers:
            raise MCPError(f"Server not registered: {server_id}")

        entry = self._servers[server_id]
        if not entry.client or not entry.client.is_connected:
            raise MCPError(f"Server not connected: {server_id}")

        return {
            "server_id": server_id,
            "tools": list(entry.capabilities.keys()),
            "resources": list(entry.resources.keys()),
            "prompts": list(entry.prompts.keys()),
        }

    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all servers and capabilities."""
        status_counts: Dict[str, int] = {}
        for entry in self._servers.values():
            status = entry.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_servers": len(self._servers),
            "total_capabilities": len(self._capabilities),
            "total_resources": len(self._resources),
            "total_prompts": len(self._prompts),
            "status_counts": status_counts,
        }

    def clear(self) -> None:
        """Clear all registrations."""
        self._servers.clear()
        self._capabilities.clear()
        self._resources.clear()
        self._prompts.clear()
