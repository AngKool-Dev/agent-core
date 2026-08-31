"""MCP errors for ARGUS."""

from typing import Optional


class MCPError(Exception):
    """Base MCP error."""

    def __init__(self, message: str, server_id: str = "", details: str = ""):
        super().__init__(message)
        self.server_id = server_id
        self.details = details


class MCPConnectionError(MCPError):
    """Raised when MCP server connection fails."""
    pass


class MCPTimeoutError(MCPError):
    """Raised when MCP operation times out."""
    pass


class MCPProtocolError(MCPError):
    """Raised on MCP protocol violation."""
    pass


class MCPServerNotFoundError(MCPError):
    """Raised when MCP server is not found."""
    pass


class MCPCapabilityError(MCPError):
    """Raised when MCP capability is invalid or unavailable."""
    pass


class MCPValidationError(MCPError):
    """Raised when MCP schema validation fails."""
    pass


class MCPAuthenticationError(MCPError):
    """Raised on MCP authentication failure."""
    pass


class MCPPermissionError(MCPError):
    """Raised when MCP operation is denied by policy."""
    pass


class MCPHealthError(MCPError):
    """Raised when MCP server health check fails."""
    pass
