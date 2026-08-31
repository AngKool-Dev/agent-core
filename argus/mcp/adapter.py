"""MCP adapter - converts MCP tools to ARGUS capabilities."""

import time
from typing import Any, Dict, List, Optional

from argus.capabilities import (
    Capability,
    CapabilityMetadata,
    CapabilitySchema,
    CapabilityType,
)
from argus.mcp.client import MCPClient
from argus.mcp.errors import MCPError
from argus.mcp.schemas import (
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPToolDefinition,
)


def _mcp_tool_to_capability_type(tool: MCPToolDefinition) -> CapabilityType:
    """Infer capability type from MCP tool definition."""
    name_lower = tool.name.lower()
    description_lower = tool.description.lower()

    if any(kw in name_lower or kw in description_lower for kw in ["read", "get", "fetch", "list", "search"]):
        return CapabilityType.READ
    elif any(kw in name_lower or kw in description_lower for kw in ["write", "create", "update", "delete", "post", "put"]):
        return CapabilityType.WRITE
    elif any(kw in name_lower or kw in description_lower for kw in ["execute", "run", "command", "shell", "bash"]):
        return CapabilityType.EXECUTE
    elif any(kw in name_lower or kw in description_lower for kw in ["browser", "navigate", "web"]):
        return CapabilityType.BROWSER
    elif any(kw in name_lower or kw in description_lower for kw in ["git", "commit", "branch"]):
        return CapabilityType.GIT
    elif any(kw in name_lower or kw in description_lower for kw in ["memory", "remember", "recall"]):
        return CapabilityType.MEMORY
    else:
        return CapabilityType.EXECUTE


def _mcp_schema_to_capability_schema(mcp_schema: Dict[str, Any]) -> CapabilitySchema:
    """Convert MCP schema to ARGUS CapabilitySchema."""
    properties = mcp_schema.get("properties", {})
    required = mcp_schema.get("required", [])

    return CapabilitySchema(
        name=mcp_schema.get("type", "object"),
        description=mcp_schema.get("description", ""),
        input_type="object",
        output_type="object",
        parameters=properties,
        required_parameters=required,
    )


class MCPCapabilityAdapter(Capability):
    """Adapts an MCP tool to an ARGUS Capability."""

    def __init__(
        self,
        metadata: CapabilityMetadata,
        tool_definition: MCPToolDefinition,
        client: MCPClient,
    ):
        super().__init__(metadata)
        self._tool_definition = tool_definition
        self._client = client

    @property
    def tool_definition(self) -> MCPToolDefinition:
        return self._tool_definition

    @property
    def server_id(self) -> str:
        return self._client.server_id

    def check_availability(self) -> bool:
        """Check if MCP tool is available."""
        return self._client.is_connected and self.metadata.availability

    def health_check(self) -> Dict[str, Any]:
        """Check MCP tool health."""
        if not self._client.is_connected:
            return {
                "status": "error",
                "message": "MCP server not connected",
                "last_check": time.time(),
            }

        return {
            "status": "healthy",
            "message": f"MCP tool {self._tool_definition.name} available",
            "last_check": time.time(),
        }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute MCP tool."""
        import asyncio

        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                self._client.call_tool(self._tool_definition.name, input_data)
            )
            execution_time = time.time() - start_time

            return {
                "success": result.get("success", False),
                "output": result.get("content"),
                "error": result.get("error"),
                "execution_time": execution_time,
                "backend": f"mcp:{self._client.server_id}",
                "fallback_used": False,
            }
        except MCPError as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "execution_time": execution_time,
                "backend": f"mcp:{self._client.server_id}",
                "fallback_used": False,
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "execution_time": execution_time,
                "backend": f"mcp:{self._client.server_id}",
                "fallback_used": False,
            }


class MCPResourceAdapter:
    """Adapts an MCP resource to an ARGUS context source."""

    def __init__(self, resource_definition: MCPResourceDefinition, client: MCPClient):
        self._resource_definition = resource_definition
        self._client = client

    @property
    def resource_definition(self) -> MCPResourceDefinition:
        return self._resource_definition

    @property
    def uri(self) -> str:
        return self._resource_definition.uri

    @property
    def name(self) -> str:
        return self._resource_definition.name

    def is_available(self) -> bool:
        """Check if resource is available."""
        return self._client.is_connected

    def read(self) -> Dict[str, Any]:
        """Read resource content."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self._client.read_resource(self._resource_definition.uri)
        )


class MCPPromptAdapter:
    """Adapts an MCP prompt to an ARGUS context candidate."""

    def __init__(self, prompt_definition: MCPPromptDefinition, client: MCPClient):
        self._prompt_definition = prompt_definition
        self._client = client

    @property
    def prompt_definition(self) -> MCPPromptDefinition:
        return self._prompt_definition

    @property
    def name(self) -> str:
        return self._prompt_definition.name

    def is_available(self) -> bool:
        """Check if prompt is available."""
        return self._client.is_connected

    def get(self, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get prompt content."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self._client.get_prompt(self._prompt_definition.name, arguments)
        )


def create_mcp_capability(
    tool_definition: MCPToolDefinition,
    client: MCPClient,
    capability_id: Optional[str] = None,
) -> MCPCapabilityAdapter:
    """Create an ARGUS capability from an MCP tool definition."""
    cap_id = capability_id or f"mcp.{client.server_id}.{tool_definition.name}"
    cap_type = _mcp_tool_to_capability_type(tool_definition)
    cap_schema = _mcp_schema_to_capability_schema(tool_definition.input_schema.__dict__)

    metadata = CapabilityMetadata(
        id=cap_id,
        name=tool_definition.name,
        description=tool_definition.description,
        type=cap_type,
        schema=cap_schema,
        tags=["mcp", f"server:{client.server_id}"],
    )

    return MCPCapabilityAdapter(metadata, tool_definition, client)
