"""Sandbox for ARGUS execution."""

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class SandboxConfig:
    """Configuration for the sandbox."""
    # Allowed directories (empty means all allowed)
    allowed_directories: List[str] = field(default_factory=list)

    # Denied directories
    denied_directories: List[str] = field(default_factory=lambda: [
        "/etc", "/sys", "/proc", "/dev", "/boot",
        "C:\\Windows", "C:\\Program Files", "C:\\ProgramData",
    ])

    # Allowed commands (empty means all allowed)
    allowed_commands: List[str] = field(default_factory=list)

    # Denied command patterns
    denied_commands: List[str] = field(default_factory=lambda: [
        r"rm\s+-rf",
        r"rm\s+-fr",
        r"dd\s+if=",
        r"mkfs",
        r"fdisk",
        r":\(\)\{ :|:& \};:",
    ])

    # Network access allowed
    network_allowed: bool = True

    # Maximum file size for writes (bytes)
    max_file_size: int = 10 * 1024 * 1024  # 10MB

    # Allow writes outside project directory
    allow_writes_outside_project: bool = False


class Sandbox:
    """Sandbox for execution."""

    def __init__(self, config: Optional[SandboxConfig] = None):
        self._config = config or SandboxConfig()

    def check_path_access(self, path: str, write: bool = False) -> bool:
        """Check if path access is allowed."""
        # Normalize path - handle both Unix and Windows paths consistently
        # Convert backslashes to forward slashes for consistent matching
        normalized = path.replace("\\", "/")
        # Remove leading slash for consistent matching
        normalized = normalized.lstrip("/")

        # Check for path traversal attempts
        if ".." in normalized:
            return False

        # Check denied directories
        for denied in self._config.denied_directories:
            denied_norm = denied.replace("\\", "/").lstrip("/")
            if normalized.startswith(denied_norm):
                return False

        # Check allowed directories (if specified)
        if self._config.allowed_directories:
            allowed = False
            for allowed_dir in self._config.allowed_directories:
                allowed_norm = allowed_dir.replace("\\", "/").lstrip("/")
                if normalized.startswith(allowed_norm):
                    allowed = True
                    break
            if not allowed:
                return False

        # Check writes outside project
        if write and not self._config.allow_writes_outside_project:
            # This would need project path context
            pass

        return True

    def check_command(self, command: str) -> bool:
        """Check if a command is allowed."""
        for pattern in self._config.denied_commands:
            if re.search(pattern, command):
                return False

        if self._config.allowed_commands:
            allowed = False
            for pattern in self._config.allowed_commands:
                if re.search(pattern, command):
                    allowed = True
                    break
            if not allowed:
                return False

        return True

    def check_file_size(self, size: int) -> bool:
        """Check if file size is within limits."""
        return size <= self._config.max_file_size

    def check_network(self) -> bool:
        """Check if network access is allowed."""
        return self._config.network_allowed

    def validate_invocation(
        self,
        capability_id: str,
        input_data: Dict[str, Any],
    ) -> tuple:
        """Validate a capability invocation.
        
        Returns (allowed: bool, reason: str).
        """
        # Check filesystem paths
        if capability_id.startswith("filesystem."):
            path = input_data.get("path", "")
            write = capability_id in ("filesystem.write", "filesystem.edit")
            if not self.check_path_access(path, write=write):
                return False, f"Path access denied: {path}"

        # Check shell commands
        if capability_id == "shell.execute":
            command = input_data.get("command", "")
            if not self.check_command(command):
                return False, f"Command denied: {command}"

        # Check network access
        if capability_id.startswith("web.") or capability_id.startswith("github."):
            if not self.check_network():
                return False, "Network access denied"

        return True, "OK"