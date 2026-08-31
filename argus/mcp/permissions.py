"""MCP permissions for ARGUS."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from argus.mcp.registry import MCPRegistry
from argus.security.permissions import Permission, SecurityPolicy


@dataclass
class MCPPermissionPolicy:
    """Permission policy for MCP servers."""
    server_id: str
    default_permission: Permission = Permission.ASK
    tool_permissions: Dict[str, Permission] = field(default_factory=dict)
    allow_resources: bool = True
    allow_prompts: bool = False
    max_tool_count: int = 50

    def get_tool_permission(self, tool_name: str) -> Permission:
        """Get permission for a specific tool."""
        return self.tool_permissions.get(tool_name, self.default_permission)

    def set_tool_permission(self, tool_name: str, permission: Permission) -> None:
        """Set permission for a specific tool."""
        self.tool_permissions[tool_name] = permission


class MCPPermissionManager:
    """Manages permissions for MCP capabilities."""

    def __init__(self, security_policy: Optional[SecurityPolicy] = None):
        self._security_policy = security_policy
        self._mcp_policies: Dict[str, MCPPermissionPolicy] = {}
        self._global_default: Permission = Permission.ASK
        self._blocked_tools: Set[str] = set()
        self._allowed_tools: Set[str] = set()

    @property
    def security_policy(self) -> Optional[SecurityPolicy]:
        return self._security_policy

    @security_policy.setter
    def security_policy(self, policy: SecurityPolicy) -> None:
        self._security_policy = policy

    def set_mcp_policy(self, server_id: str, policy: MCPPermissionPolicy) -> None:
        """Set permission policy for an MCP server."""
        self._mcp_policies[server_id] = policy

    def get_mcp_policy(self, server_id: str) -> Optional[MCPPermissionPolicy]:
        """Get permission policy for an MCP server."""
        return self._mcp_policies.get(server_id)

    def remove_mcp_policy(self, server_id: str) -> bool:
        """Remove permission policy for an MCP server."""
        if server_id in self._mcp_policies:
            del self._mcp_policies[server_id]
            return True
        return False

    def evaluate_tool_permission(
        self,
        server_id: str,
        tool_name: str,
        capability_id: str,
    ) -> Permission:
        """Evaluate permission for an MCP tool."""
        full_tool_id = f"mcp.{server_id}.{tool_name}"

        if full_tool_id in self._blocked_tools:
            return Permission.DENY

        if full_tool_id in self._allowed_tools:
            return Permission.ALLOW

        mcp_policy = self._mcp_policies.get(server_id)
        if mcp_policy:
            permission = mcp_policy.get_tool_permission(tool_name)
            if permission != Permission.ASK:
                return permission

        if self._security_policy:
            permission = self._security_policy.get_capability_permission(capability_id)
            return permission

        return self._global_default

    def block_tool(self, server_id: str, tool_name: str) -> None:
        """Block a specific MCP tool."""
        self._blocked_tools.add(f"mcp.{server_id}.{tool_name}")

    def allow_tool(self, server_id: str, tool_name: str) -> None:
        """Allow a specific MCP tool."""
        self._allowed_tools.add(f"mcp.{server_id}.{tool_name}")
        self._blocked_tools.discard(f"mcp.{server_id}.{tool_name}")

    def unblock_tool(self, server_id: str, tool_name: str) -> None:
        """Unblock a specific MCP tool."""
        self._blocked_tools.discard(f"mcp.{server_id}.{tool_name}")

    def unallow_tool(self, server_id: str, tool_name: str) -> None:
        """Remove a tool from the allowed list."""
        self._allowed_tools.discard(f"mcp.{server_id}.{tool_name}")

    def is_tool_allowed(self, server_id: str, tool_name: str) -> bool:
        """Check if a tool is explicitly allowed."""
        return f"mcp.{server_id}.{tool_name}" in self._allowed_tools

    def is_tool_blocked(self, server_id: str, tool_name: str) -> bool:
        """Check if a tool is explicitly blocked."""
        return f"mcp.{server_id}.{tool_name}" in self._blocked_tools

    def set_global_default(self, permission: Permission) -> None:
        """Set the global default permission for MCP tools."""
        self._global_default = permission

    def should_redact_content(self, server_id: str) -> bool:
        """Check if MCP content should be redacted."""
        return True

    def get_redaction_patterns(self, server_id: str) -> List[str]:
        """Get redaction patterns for an MCP server."""
        return []

    def filter_capabilities(
        self,
        capabilities: List[Any],
        server_id: str,
    ) -> List[Any]:
        """Filter capabilities based on permissions."""
        filtered = []
        for cap in capabilities:
            tool_name = cap.metadata.id.split(".")[-1] if hasattr(cap, "metadata") else ""
            permission = self.evaluate_tool_permission(server_id, tool_name, cap.metadata.id if hasattr(cap, "metadata") else "")
            if permission != Permission.DENY:
                filtered.append(cap)
        return filtered

    def get_status(self) -> Dict[str, Any]:
        """Get permission manager status."""
        return {
            "global_default": self._global_default.value,
            "mcp_policies": len(self._mcp_policies),
            "blocked_tools": len(self._blocked_tools),
            "allowed_tools": len(self._allowed_tools),
        }
