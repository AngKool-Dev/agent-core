"""ARGUS MCP capability adapter subsystem."""

from argus.mcp.adapter import (
    MCPCapabilityAdapter,
    MCPPromptAdapter,
    MCPResourceAdapter,
    create_mcp_capability,
)
from argus.mcp.client import MCPClient, MCPClientState
from argus.mcp.discovery import MCPDiscovery, MCPServerConfig
from argus.mcp.errors import (
    MCPCapabilityError,
    MCPConnectionError,
    MCPError,
    MCPHealthError,
    MCPPermissionError,
    MCPProtocolError,
    MCPServerNotFoundError,
    MCPTimeoutError,
    MCPValidationError,
)
from argus.mcp.health import (
    HealthCheckResult,
    HealthStatus,
    MCPHealthMonitor,
    ServerHealth,
)
from argus.mcp.lifecycle import (
    LifecycleEvent,
    LifecycleEventData,
    MCPLifecycleManager,
)
from argus.mcp.permissions import MCPPermissionManager, MCPPermissionPolicy
from argus.mcp.registry import (
    MCPServerEntry,
    MCPRegistry,
    ServerStatus,
)
from argus.mcp.schemas import (
    MCPParameter,
    MCPParameterType,
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPSchema,
    MCPServerInfo,
    MCPToolDefinition,
    SchemaNormalizer,
)
from argus.mcp.transport import (
    MCPMessage,
    SSETransport,
    StdioTransport,
    TransportConfig,
    TransportType,
    create_transport,
)

__all__ = [
    # Adapter
    "MCPCapabilityAdapter",
    "MCPPromptAdapter",
    "MCPResourceAdapter",
    "create_mcp_capability",
    # Client
    "MCPClient",
    "MCPClientState",
    # Discovery
    "MCPDiscovery",
    "MCPServerConfig",
    # Errors
    "MCPError",
    "MCPConnectionError",
    "MCPTimeoutError",
    "MCPProtocolError",
    "MCPServerNotFoundError",
    "MCPCapabilityError",
    "MCPValidationError",
    "MCPPermissionError",
    "MCPHealthError",
    # Health
    "HealthCheckResult",
    "HealthStatus",
    "MCPHealthMonitor",
    "ServerHealth",
    # Lifecycle
    "LifecycleEvent",
    "LifecycleEventData",
    "MCPLifecycleManager",
    # Permissions
    "MCPPermissionManager",
    "MCPPermissionPolicy",
    # Registry
    "MCPServerEntry",
    "MCPRegistry",
    "ServerStatus",
    # Schemas
    "MCPParameter",
    "MCPParameterType",
    "MCPPromptDefinition",
    "MCPResourceDefinition",
    "MCPSchema",
    "MCPServerInfo",
    "MCPToolDefinition",
    "SchemaNormalizer",
    # Transport
    "MCPMessage",
    "StdioTransport",
    "SSETransport",
    "TransportConfig",
    "TransportType",
    "create_transport",
]
