"""MCP schema normalization for ARGUS."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MCPParameterType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


@dataclass
class MCPParameter:
    """Normalized MCP parameter."""
    name: str
    type: MCPParameterType
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None
    items: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None


@dataclass
class MCPSchema:
    """Normalized MCP schema."""
    type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    additional_properties: bool = False


@dataclass
class MCPToolDefinition:
    """Normalized MCP tool definition."""
    name: str
    description: str
    input_schema: MCPSchema
    server_id: str = ""
    annotations: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResourceDefinition:
    """Normalized MCP resource definition."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = ""
    server_id: str = ""


@dataclass
class MCPPromptDefinition:
    """Normalized MCP prompt definition."""
    name: str
    description: str = ""
    arguments: List[MCPParameter] = field(default_factory=list)
    server_id: str = ""


@dataclass
class MCPServerInfo:
    """MCP server information."""
    name: str
    version: str
    capabilities: Dict[str, Any] = field(default_factory=dict)
    instructions: str = ""


class SchemaNormalizer:
    """Normalizes MCP schemas to ARGUS-native format."""

    def __init__(self):
        self._type_mapping = {
            "string": MCPParameterType.STRING,
            "number": MCPParameterType.NUMBER,
            "integer": MCPParameterType.INTEGER,
            "boolean": MCPParameterType.BOOLEAN,
            "array": MCPParameterType.ARRAY,
            "object": MCPParameterType.OBJECT,
            "null": MCPParameterType.NULL,
        }

    def normalize_tool(self, raw_tool: Dict[str, Any], server_id: str = "") -> MCPToolDefinition:
        """Normalize a raw MCP tool definition."""
        name = self._normalize_name(raw_tool.get("name", ""))
        description = self._normalize_description(raw_tool.get("description", ""))
        input_schema = self._normalize_schema(raw_tool.get("inputSchema", {}))
        annotations = raw_tool.get("annotations", {})

        return MCPToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            server_id=server_id,
            annotations=annotations,
        )

    def normalize_resource(self, raw_resource: Dict[str, Any], server_id: str = "") -> MCPResourceDefinition:
        """Normalize a raw MCP resource definition."""
        return MCPResourceDefinition(
            uri=raw_resource.get("uri", ""),
            name=raw_resource.get("name", ""),
            description=raw_resource.get("description", ""),
            mime_type=raw_resource.get("mimeType", ""),
            server_id=server_id,
        )

    def normalize_prompt(self, raw_prompt: Dict[str, Any], server_id: str = "") -> MCPPromptDefinition:
        """Normalize a raw MCP prompt definition."""
        arguments = []
        for arg in raw_prompt.get("arguments", []):
            arguments.append(MCPParameter(
                name=arg.get("name", ""),
                type=MCPParameterType.STRING,
                description=arg.get("description", ""),
                required=arg.get("required", False),
            ))

        return MCPPromptDefinition(
            name=raw_prompt.get("name", ""),
            description=raw_prompt.get("description", ""),
            arguments=arguments,
            server_id=server_id,
        )

    def normalize_schema(self, raw_schema: Dict[str, Any]) -> MCPSchema:
        """Normalize a raw JSON schema."""
        return self._normalize_schema(raw_schema)

    def _normalize_name(self, name: str) -> str:
        """Normalize a tool/resource name."""
        normalized = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
        normalized = re.sub(r'_+', '_', normalized)
        normalized = normalized.strip('_')
        return normalized.lower()

    def _normalize_description(self, description: str) -> str:
        """Normalize a description."""
        cleaned = ' '.join(description.split())
        return cleaned[:1000]

    def _normalize_schema(self, raw_schema: Dict[str, Any]) -> MCPSchema:
        """Normalize a JSON schema."""
        if not raw_schema:
            return MCPSchema()

        schema_type = raw_schema.get("type", "object")
        if schema_type not in ("object", "array", "string", "number", "integer", "boolean", "null"):
            schema_type = "object"

        properties = raw_schema.get("properties", {})
        normalized_properties = {}
        for prop_name, prop_schema in properties.items():
            normalized_properties[self._normalize_name(prop_name)] = self._normalize_property(prop_schema)

        required = raw_schema.get("required", [])
        normalized_required = [self._normalize_name(r) for r in required]

        return MCPSchema(
            type=schema_type,
            properties=normalized_properties,
            required=normalized_required,
            additional_properties=raw_schema.get("additionalProperties", False),
        )

    def _normalize_property(self, prop_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a property schema."""
        if not isinstance(prop_schema, dict):
            return {"type": "string"}

        normalized = {}
        if "type" in prop_schema:
            normalized["type"] = prop_schema["type"]
        if "description" in prop_schema:
            normalized["description"] = self._normalize_description(prop_schema["description"])
        if "default" in prop_schema:
            normalized["default"] = prop_schema["default"]
        if "enum" in prop_schema:
            normalized["enum"] = prop_schema["enum"]
        if "items" in prop_schema and isinstance(prop_schema["items"], dict):
            normalized["items"] = self._normalize_property(prop_schema["items"])
        if "properties" in prop_schema and isinstance(prop_schema["properties"], dict):
            normalized["properties"] = {
                self._normalize_name(k): self._normalize_property(v)
                for k, v in prop_schema["properties"].items()
            }

        return normalized

    def validate_tool_definition(self, tool: Dict[str, Any]) -> List[str]:
        """Validate a raw MCP tool definition. Returns list of errors."""
        errors = []

        if not tool.get("name"):
            errors.append("Tool missing required 'name' field")

        if not tool.get("inputSchema"):
            errors.append("Tool missing required 'inputSchema' field")
        elif not isinstance(tool.get("inputSchema"), dict):
            errors.append("Tool 'inputSchema' must be an object")

        return errors

    def validate_resource_definition(self, resource: Dict[str, Any]) -> List[str]:
        """Validate a raw MCP resource definition. Returns list of errors."""
        errors = []

        if not resource.get("uri"):
            errors.append("Resource missing required 'uri' field")
        if not resource.get("name"):
            errors.append("Resource missing required 'name' field")

        return errors

    def validate_prompt_definition(self, prompt: Dict[str, Any]) -> List[str]:
        """Validate a raw MCP prompt definition. Returns list of errors."""
        errors = []

        if not prompt.get("name"):
            errors.append("Prompt missing required 'name' field")

        return errors
