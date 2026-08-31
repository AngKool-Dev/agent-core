"""Permission policies for ARGUS."""

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class Permission(str, Enum):
    """Permission levels."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PathScope:
    """A path scope for filesystem permissions."""
    pattern: str
    permission: Permission
    description: str = ""

    def matches(self, path: str) -> bool:
        """Check if a path matches this scope."""
        # Normalize path for matching
        normalized = path.replace("\\", "/")
        pattern = self.pattern.replace("\\", "/")
        return fnmatch.fnmatch(normalized, pattern)


@dataclass
class SecurityPolicy:
    """Security policy for capabilities."""

    # Global default
    default_permission: Permission = Permission.ASK

    # Capability-specific permissions
    capabilities: Dict[str, Permission] = field(default_factory=dict)

    # Path scopes for filesystem operations
    path_scopes: List[PathScope] = field(default_factory=list)

    # Allowed commands (for shell)
    allowed_commands: List[str] = field(default_factory=list)

    # Denied commands (for shell)
    denied_commands: List[str] = field(default_factory=list)

    # Maximum risk level allowed without approval
    max_risk_level: str = "medium"

    # Require approval for these capabilities
    require_approval: Set[str] = field(default_factory=set)

    # Deny these capabilities entirely
    denied_capabilities: Set[str] = field(default_factory=set)

    def get_capability_permission(self, capability_id: str) -> Permission:
        """Get permission for a capability."""
        return self.capabilities.get(capability_id, self.default_permission)

    def set_capability_permission(self, capability_id: str, permission: Permission) -> None:
        """Set permission for a capability."""
        self.capabilities[capability_id] = permission

    def add_path_scope(self, pattern: str, permission: Permission, description: str = "") -> None:
        """Add a path scope."""
        self.path_scopes.append(PathScope(pattern=pattern, permission=permission, description=description))

    def check_path(self, path: str) -> Permission:
        """Check permission for a path."""
        # Check scopes in order (last match wins)
        matching_permission = None
        for scope in self.path_scopes:
            if scope.matches(path):
                matching_permission = scope.permission

        return matching_permission or self.default_permission

    def check_command(self, command: str) -> Permission:
        """Check permission for a shell command."""
        # Check denied commands first
        for pattern in self.denied_commands:
            if re.search(pattern, command, re.IGNORECASE):
                return Permission.DENY

        # Check allowed commands
        for pattern in self.allowed_commands:
            if re.search(pattern, command, re.IGNORECASE):
                return Permission.ALLOW

        return self.default_permission


def create_default_policy() -> SecurityPolicy:
    """Create a sensible default security policy."""
    policy = SecurityPolicy(default_permission=Permission.ASK)

    # Filesystem
    policy.set_capability_permission("filesystem.read", Permission.ALLOW)
    policy.set_capability_permission("filesystem.list_dir", Permission.ALLOW)
    policy.set_capability_permission("filesystem.write", Permission.ASK)
    policy.set_capability_permission("filesystem.edit", Permission.ALLOW)

    # Git
    policy.set_capability_permission("git.status", Permission.ALLOW)
    policy.set_capability_permission("git.diff", Permission.ALLOW)
    policy.set_capability_permission("git.log", Permission.ALLOW)
    policy.set_capability_permission("git.add", Permission.ASK)
    policy.set_capability_permission("git.commit", Permission.ASK)
    policy.set_capability_permission("git.workflow", Permission.ASK)

    # Shell
    policy.set_capability_permission("shell.execute", Permission.ASK)

    # Browser
    policy.set_capability_permission("browser.navigate", Permission.ALLOW)
    policy.set_capability_permission("browser.screenshot", Permission.ALLOW)

    # Search
    policy.set_capability_permission("search.grep", Permission.ALLOW)
    policy.set_capability_permission("search.glob", Permission.ALLOW)

    # Memory
    policy.set_capability_permission("memory.read", Permission.ALLOW)
    policy.set_capability_permission("memory.search", Permission.ALLOW)
    policy.set_capability_permission("memory.store", Permission.ALLOW)

    # Reach
    policy.set_capability_permission("web.read", Permission.ALLOW)
    policy.set_capability_permission("web.search", Permission.ALLOW)
    policy.set_capability_permission("github.get_repo", Permission.ALLOW)
    policy.set_capability_permission("github.search_repos", Permission.ALLOW)
    policy.set_capability_permission("github.search_issues", Permission.ALLOW)
    policy.set_capability_permission("github.get_issue", Permission.ALLOW)
    policy.set_capability_permission("github.list_issues", Permission.ALLOW)
    policy.set_capability_permission("github.create_issue", Permission.ASK)
    policy.set_capability_permission("youtube.get_info", Permission.ALLOW)
    policy.set_capability_permission("youtube.search", Permission.ALLOW)
    policy.set_capability_permission("reddit.search", Permission.ALLOW)
    policy.set_capability_permission("reddit.get_subreddit", Permission.ALLOW)
    policy.set_capability_permission("reddit.get_post", Permission.ALLOW)
    policy.set_capability_permission("reddit.get_user", Permission.ALLOW)

    # Model
    policy.set_capability_permission("model.generate", Permission.ALLOW)

    # Path scopes - allow project directory
    policy.add_path_scope(
        pattern="*",
        permission=Permission.ALLOW,
        description="Allow project directory",
    )

    # Deny destructive commands
    policy.denied_commands = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r"rm\s+-rf\s+\*",
        r"rm\s+-rf\s+\.",
        r"dd\s+if=",
        r"mkfs\b",
        r"fdisk\b",
        r":\(\)\{ :|:& \};:",  # fork bomb
    ]

    # Require approval for sensitive operations
    policy.require_approval = {
        "shell.execute",
        "git.commit",
        "git.push",
        "filesystem.write",
    }

    return policy


def create_restrictive_policy() -> SecurityPolicy:
    """Create a restrictive security policy."""
    policy = SecurityPolicy(default_permission=Permission.DENY)

    # Only allow read operations
    policy.set_capability_permission("filesystem.read", Permission.ALLOW)
    policy.set_capability_permission("filesystem.list_dir", Permission.ALLOW)
    policy.set_capability_permission("git.status", Permission.ALLOW)
    policy.set_capability_permission("git.diff", Permission.ALLOW)
    policy.set_capability_permission("git.log", Permission.ALLOW)
    policy.set_capability_permission("search.grep", Permission.ALLOW)
    policy.set_capability_permission("search.glob", Permission.ALLOW)
    policy.set_capability_permission("memory.search", Permission.ALLOW)
    policy.set_capability_permission("web.read", Permission.ALLOW)
    policy.set_capability_permission("web.search", Permission.ALLOW)

    return policy


def create_permissive_policy() -> SecurityPolicy:
    """Create a permissive security policy (for trusted environments)."""
    policy = SecurityPolicy(default_permission=Permission.ALLOW)

    # Allow most operations
    for cap in [
        "filesystem.read", "filesystem.list_dir", "filesystem.write", "filesystem.edit",
        "git.status", "git.diff", "git.log", "git.add", "git.commit",
        "browser.navigate", "browser.screenshot",
        "search.grep", "search.glob",
        "memory.read", "memory.search", "memory.store",
        "web.read", "web.search",
        "github.get_repo", "github.search_repos", "github.search_issues",
        "github.get_issue", "github.list_issues", "github.create_issue",
        "youtube.get_info", "youtube.search",
        "reddit.search", "reddit.get_subreddit", "reddit.get_post", "reddit.get_user",
        "model.generate",
    ]:
        policy.set_capability_permission(cap, Permission.ALLOW)

    # Shell still requires approval
    policy.set_capability_permission("shell.execute", Permission.ASK)

    return policy