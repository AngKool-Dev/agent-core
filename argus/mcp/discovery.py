"""MCP discovery for ARGUS."""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.mcp.errors import MCPError
from argus.mcp.transport import TransportConfig, TransportType


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    server_id: str
    transport_type: TransportType = TransportType.STDIO
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    enabled: bool = True
    trust_level: str = "untrusted"
    permissions: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPDiscovery:
    """Discovers and configures MCP servers."""

    def __init__(self):
        self._configs: Dict[str, MCPServerConfig] = {}

    def add_server(self, config: MCPServerConfig) -> None:
        """Add a server configuration."""
        self._configs[config.server_id] = config

    def remove_server(self, server_id: str) -> bool:
        """Remove a server configuration."""
        if server_id in self._configs:
            del self._configs[server_id]
            return True
        return False

    def get_server(self, server_id: str) -> Optional[MCPServerConfig]:
        """Get a server configuration."""
        return self._configs.get(server_id)

    def get_all_servers(self) -> List[MCPServerConfig]:
        """Get all server configurations."""
        return list(self._configs.values())

    def get_enabled_servers(self) -> List[MCPServerConfig]:
        """Get enabled server configurations."""
        return [c for c in self._configs.values() if c.enabled]

    def load_from_dict(self, data: Dict[str, Any]) -> List[MCPServerConfig]:
        """Load server configurations from a dictionary."""
        configs = []

        for server_id, server_data in data.items():
            config = MCPServerConfig(
                server_id=server_id,
                transport_type=TransportType(server_data.get("transport", "stdio")),
                command=server_data.get("command", ""),
                args=server_data.get("args", []),
                env=server_data.get("env", {}),
                url=server_data.get("url", ""),
                headers=server_data.get("headers", {}),
                timeout=server_data.get("timeout", 30.0),
                enabled=server_data.get("enabled", True),
                trust_level=server_data.get("trust_level", "untrusted"),
                permissions=server_data.get("permissions", {}),
                metadata=server_data.get("metadata", {}),
            )
            self._configs[server_id] = config
            configs.append(config)

        return configs

    def load_from_env(self, prefix: str = "ARGUS_MCP_") -> List[MCPServerConfig]:
        """Load server configurations from environment variables."""
        configs = []
        env_vars = {k: v for k, v in os.environ.items() if k.startswith(prefix)}

        server_ids = set()
        for key in env_vars:
            parts = key[len(prefix):].split("_")
            if parts:
                server_ids.add(parts[0].lower())

        for server_id in server_ids:
            command_key = f"{prefix}{server_id.upper()}_COMMAND"
            if command_key in env_vars:
                config = MCPServerConfig(
                    server_id=server_id,
                    command=env_vars[command_key],
                    args=env_vars.get(f"{prefix}{server_id.upper()}_ARGS", "").split(),
                    enabled=env_vars.get(f"{prefix}{server_id.upper()}_ENABLED", "true").lower() == "true",
                )
                self._configs[server_id] = config
                configs.append(config)

        return configs

    def create_transport_config(self, server_config: MCPServerConfig) -> TransportConfig:
        """Create a transport config from a server config."""
        return TransportConfig(
            type=server_config.transport_type,
            command=server_config.command,
            args=server_config.args,
            env=server_config.env,
            url=server_config.url,
            headers=server_config.headers,
            timeout=server_config.timeout,
        )

    def validate_config(self, config: MCPServerConfig) -> List[str]:
        """Validate a server configuration."""
        errors = []

        if not config.server_id:
            errors.append("Server ID is required")

        if config.transport_type == TransportType.STDIO:
            if not config.command:
                errors.append("Command is required for stdio transport")
        elif config.transport_type in (TransportType.SSE, TransportType.HTTP):
            if not config.url:
                errors.append("URL is required for SSE/HTTP transport")

        if config.timeout <= 0:
            errors.append("Timeout must be positive")

        return errors

    def create_default_filesystem_server(self, base_path: str = ".") -> MCPServerConfig:
        """Create a default filesystem MCP server configuration."""
        return MCPServerConfig(
            server_id="filesystem",
            transport_type=TransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", base_path],
            enabled=True,
            trust_level="untrusted",
            metadata={"description": "Local filesystem access via MCP"},
        )

    def create_default_github_server(self) -> MCPServerConfig:
        """Create a default GitHub MCP server configuration."""
        return MCPServerConfig(
            server_id="github",
            transport_type=TransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            enabled=False,
            trust_level="untrusted",
            metadata={"description": "GitHub API access via MCP"},
        )

    def create_default_postgres_server(self, connection_string: str = "") -> MCPServerConfig:
        """Create a default Postgres MCP server configuration."""
        args = ["-y", "@modelcontextprotocol/server-postgres"]
        if connection_string:
            args.append(connection_string)

        return MCPServerConfig(
            server_id="postgres",
            transport_type=TransportType.STDIO,
            command="npx",
            args=args,
            enabled=False,
            trust_level="untrusted",
            metadata={"description": "PostgreSQL database access via MCP"},
        )
