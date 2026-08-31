"""MCP client for ARGUS."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.mcp.errors import (
    MCPCapabilityError,
    MCPConnectionError,
    MCPError,
    MCPProtocolError,
    MCPTimeoutError,
)
from argus.mcp.schemas import (
    MCPParameter,
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPSchema,
    MCPServerInfo,
    MCPToolDefinition,
    SchemaNormalizer,
)
from argus.mcp.transport import (
    MCPMessage,
    StdioTransport,
    TransportConfig,
    TransportType,
    create_transport,
)


@dataclass
class MCPClientState:
    """State of an MCP client."""
    connected: bool = False
    initialized: bool = False
    server_info: Optional[MCPServerInfo] = None
    tools: Dict[str, MCPToolDefinition] = field(default_factory=dict)
    resources: Dict[str, MCPResourceDefinition] = field(default_factory=dict)
    prompts: Dict[str, MCPPromptDefinition] = field(default_factory=dict)
    last_error: str = ""
    last_activity: float = 0.0


class MCPClient:
    """MCP protocol client."""

    def __init__(self, server_id: str, config: TransportConfig):
        self._server_id = server_id
        self._config = config
        self._transport = create_transport(config)
        self._state = MCPClientState()
        self._normalizer = SchemaNormalizer()

    @property
    def server_id(self) -> str:
        return self._server_id

    @property
    def state(self) -> MCPClientState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state.connected

    @property
    def is_initialized(self) -> str:
        return self._state.initialized

    async def connect(self) -> None:
        """Connect to MCP server."""
        try:
            await self._transport.connect()
            self._state.connected = True
            self._state.last_activity = time.time()
        except MCPConnectionError:
            raise
        except Exception as e:
            raise MCPConnectionError(
                f"Failed to connect to MCP server: {e}",
                server_id=self._server_id,
            )

    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        await self._transport.disconnect()
        self._state.connected = False
        self._state.initialized = False

    async def initialize(self) -> MCPServerInfo:
        """Initialize MCP session."""
        if not self._state.connected:
            raise MCPConnectionError("Not connected", server_id=self._server_id)

        request = MCPMessage.request(
            id=str(uuid.uuid4())[:8],
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "argus",
                    "version": "1.0.0",
                },
            },
        )

        response = await self._transport.send(request)

        if response.error:
            raise MCPProtocolError(
                f"Initialize failed: {response.error.get('message', 'Unknown error')}",
                server_id=self._server_id,
            )

        result = response.result or {}
        server_info = MCPServerInfo(
            name=result.get("serverInfo", {}).get("name", "unknown"),
            version=result.get("serverInfo", {}).get("version", "0.0.0"),
            capabilities=result.get("capabilities", {}),
            instructions=result.get("instructions", ""),
        )

        self._state.server_info = server_info
        self._state.initialized = True
        self._state.last_activity = time.time()

        await self._transport.send_notification(
            MCPMessage.notification("notifications/initialized")
        )

        return server_info

    async def list_tools(self) -> List[MCPToolDefinition]:
        """List available tools from MCP server."""
        if not self._state.initialized:
            raise MCPError("Not initialized", server_id=self._server_id)

        request = MCPMessage.request(
            id=str(uuid.uuid4())[:8],
            method="tools/list",
            params={},
        )

        response = await self._transport.send(request)

        if response.error:
            raise MCPCapabilityError(
                f"Failed to list tools: {response.error.get('message', 'Unknown error')}",
                server_id=self._server_id,
            )

        result = response.result or {}
        raw_tools = result.get("tools", [])

        tools = []
        for raw_tool in raw_tools:
            errors = self._normalizer.validate_tool_definition(raw_tool)
            if errors:
                continue

            tool = self._normalizer.normalize_tool(raw_tool, self._server_id)
            tools.append(tool)
            self._state.tools[tool.name] = tool

        self._state.last_activity = time.time()
        return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call an MCP tool."""
        if not self._state.initialized:
            raise MCPError("Not initialized", server_id=self._server_id)

        if tool_name not in self._state.tools:
            raise MCPCapabilityError(
                f"Tool not found: {tool_name}",
                server_id=self._server_id,
            )

        request = MCPMessage.request(
            id=str(uuid.uuid4())[:8],
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments or {},
            },
        )

        response = await self._transport.send(request)

        if response.error:
            return {
                "success": False,
                "error": response.error.get("message", "Unknown error"),
                "content": None,
            }

        result = response.result or {}
        content = result.get("content", [])
        is_error = result.get("isError", False)

        self._state.last_activity = time.time()

        return {
            "success": not is_error,
            "error": None,
            "content": content,
        }

    async def list_resources(self) -> List[MCPResourceDefinition]:
        """List available resources from MCP server."""
        if not self._state.initialized:
            raise MCPError("Not initialized", server_id=self._server_id)

        request = MCPMessage.request(
            id=str(uuid.uuid4())[:8],
            method="resources/list",
            params={},
        )

        response = await self._transport.send(request)

        if response.error:
            raise MCPCapabilityError(
                f"Failed to list resources: {response.error.get('message', 'Unknown error')}",
                server_id=self._server_id,
            )

        result = response.result or {}
        raw_resources = result.get("resources", [])

        resources = []
        for raw_resource in raw_resources:
            errors = self._normalizer.validate_resource_definition(raw_resource)
            if errors:
                continue

            resource = self._normalizer.normalize_resource(raw_resource, self._server_id)
            resources.append(resource)
            self._state.resources[resource.uri] = resource

        self._state.last_activity = time.time()
        return resources

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read an MCP resource."""
        if not self._state.initialized:
            raise MCPError("Not initialized", server_id=self._server_id)

        if uri not in self._state.resources:
            raise MCPCapabilityError(
                f"Resource not found: {uri}",
                server_id=self._server_id,
            )

        request = MCPMessage.request(
            id=str(uuid.uuid4())[:8],
            method="resources/read",
            params={"uri": uri},
        )

        response = await self._transport.send(request)

        if response.error:
            return {
                "success": False,
                "error": response.error.get("message", "Unknown error"),
                "contents": None,
            }

        result = response.result or {}
        self._state.last_activity = time.time()

        return {
            "success": True,
            "error": None,
            "contents": result.get("contents", []),
        }

    async def list_prompts(self) -> List[MCPPromptDefinition]:
        """List available prompts from MCP server."""
        if not self._state.initialized:
            raise MCPError("Not initialized", server_id=self._server_id)

        request = MCPMessage.request(
            id=str(uuid.uuid4())[:8],
            method="prompts/list",
            params={},
        )

        response = await self._transport.send(request)

        if response.error:
            raise MCPCapabilityError(
                f"Failed to list prompts: {response.error.get('message', 'Unknown error')}",
                server_id=self._server_id,
            )

        result = response.result or {}
        raw_prompts = result.get("prompts", [])

        prompts = []
        for raw_prompt in raw_prompts:
            errors = self._normalizer.validate_prompt_definition(raw_prompt)
            if errors:
                continue

            prompt = self._normalizer.normalize_prompt(raw_prompt, self._server_id)
            prompts.append(prompt)
            self._state.prompts[prompt.name] = prompt

        self._state.last_activity = time.time()
        return prompts

    async def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get an MCP prompt."""
        if not self._state.initialized:
            raise MCPError("Not initialized", server_id=self._server_id)

        if name not in self._state.prompts:
            raise MCPCapabilityError(
                f"Prompt not found: {name}",
                server_id=self._server_id,
            )

        request = MCPMessage.request(
            id=str(uuid.uuid4())[:8],
            method="prompts/get",
            params={
                "name": name,
                "arguments": arguments or {},
            },
        )

        response = await self._transport.send(request)

        if response.error:
            return {
                "success": False,
                "error": response.error.get("message", "Unknown error"),
                "messages": None,
            }

        result = response.result or {}
        self._state.last_activity = time.time()

        return {
            "success": True,
            "error": None,
            "description": result.get("description", ""),
            "messages": result.get("messages", []),
        }

    def get_tool(self, tool_name: str) -> Optional[MCPToolDefinition]:
        """Get a tool definition by name."""
        return self._state.tools.get(tool_name)

    def get_resource(self, uri: str) -> Optional[MCPResourceDefinition]:
        """Get a resource definition by URI."""
        return self._state.resources.get(uri)

    def get_prompt(self, name: str) -> Optional[MCPPromptDefinition]:
        """Get a prompt definition by name."""
        return self._state.prompts.get(name)
