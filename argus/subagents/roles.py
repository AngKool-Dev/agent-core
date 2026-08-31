"""Subagent roles for ARGUS."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.subagents.models import SubagentRole


@dataclass(frozen=True)
class RoleDefinition:
    """Definition of a subagent role."""
    role_id: SubagentRole
    description: str
    default_capabilities: List[str] = field(default_factory=list)
    denied_capabilities: List[str] = field(default_factory=list)
    allowed_operations: List[str] = field(default_factory=list)
    denied_operations: List[str] = field(default_factory=list)
    default_limits: Dict[str, int] = field(default_factory=dict)
    can_create_children: bool = False
    max_children: int = 0


# Default role definitions
DEFAULT_ROLES: Dict[SubagentRole, RoleDefinition] = {
    SubagentRole.RESEARCHER: RoleDefinition(
        role_id=SubagentRole.RESEARCHER,
        description="Investigates and gathers evidence without modifying files",
        default_capabilities=[
            "reach.read",
            "browser.read",
            "repository.read",
            "filesystem.read",
            "search.grep",
            "search.glob",
            "memory.search",
            "web.read",
            "github.get_repo",
            "github.get_readme",
            "github.search_repos",
        ],
        denied_capabilities=[
            "filesystem.write",
            "filesystem.edit",
            "shell.execute",
            "git.commit",
            "git.push",
        ],
        allowed_operations=["read", "search", "analyze"],
        denied_operations=["write", "execute", "modify", "delete"],
        default_limits={
            "max_model_calls": 20,
            "max_tool_calls": 30,
            "max_iterations": 10,
            "max_time_seconds": 300,
            "max_recovery_attempts": 2,
            "max_child_agents": 0,
        },
        can_create_children=False,
        max_children=0,
    ),

    SubagentRole.IMPLEMENTER: RoleDefinition(
        role_id=SubagentRole.IMPLEMENTER,
        description="Implements code changes within scoped boundaries",
        default_capabilities=[
            "filesystem.read",
            "filesystem.write",
            "filesystem.edit",
            "shell.execute",
            "search.grep",
            "search.glob",
            "git.status",
            "git.diff",
            "git.add",
            "repository.read",
        ],
        denied_capabilities=[
            "git.push",
            "git.commit",
        ],
        allowed_operations=["read", "write", "execute", "search"],
        denied_operations=["push", "force_delete"],
        default_limits={
            "max_model_calls": 30,
            "max_tool_calls": 50,
            "max_iterations": 15,
            "max_time_seconds": 600,
            "max_recovery_attempts": 3,
            "max_child_agents": 0,
        },
        can_create_children=False,
        max_children=0,
    ),

    SubagentRole.TESTER: RoleDefinition(
        role_id=SubagentRole.TESTER,
        description="Runs tests and validates behavior",
        default_capabilities=[
            "filesystem.read",
            "shell.execute",
            "search.grep",
            "search.glob",
            "git.status",
            "git.diff",
            "repository.read",
        ],
        denied_capabilities=[
            "filesystem.write",
            "filesystem.edit",
            "git.commit",
            "git.push",
        ],
        allowed_operations=["read", "execute", "test"],
        denied_operations=["write", "modify"],
        default_limits={
            "max_model_calls": 15,
            "max_tool_calls": 25,
            "max_iterations": 8,
            "max_time_seconds": 300,
            "max_recovery_attempts": 2,
            "max_child_agents": 0,
        },
        can_create_children=False,
        max_children=0,
    ),

    SubagentRole.REVIEWER: RoleDefinition(
        role_id=SubagentRole.REVIEWER,
        description="Reviews code and provides evidence-based feedback",
        default_capabilities=[
            "filesystem.read",
            "search.grep",
            "search.glob",
            "git.status",
            "git.diff",
            "git.log",
            "repository.read",
            "verification.read",
            "review.read",
        ],
        denied_capabilities=[
            "filesystem.write",
            "filesystem.edit",
            "shell.execute",
            "git.commit",
            "git.push",
        ],
        allowed_operations=["read", "analyze", "review"],
        denied_operations=["write", "execute", "modify"],
        default_limits={
            "max_model_calls": 20,
            "max_tool_calls": 30,
            "max_iterations": 10,
            "max_time_seconds": 300,
            "max_recovery_attempts": 1,
            "max_child_agents": 0,
        },
        can_create_children=False,
        max_children=0,
    ),

    SubagentRole.DEBUGGER: RoleDefinition(
        role_id=SubagentRole.DEBUGGER,
        description="Diagnoses and fixes bugs within scoped boundaries",
        default_capabilities=[
            "filesystem.read",
            "filesystem.write",
            "filesystem.edit",
            "shell.execute",
            "search.grep",
            "search.glob",
            "git.status",
            "git.diff",
            "repository.read",
        ],
        denied_capabilities=[
            "git.push",
        ],
        allowed_operations=["read", "write", "execute", "debug"],
        denied_operations=["push"],
        default_limits={
            "max_model_calls": 25,
            "max_tool_calls": 40,
            "max_iterations": 12,
            "max_time_seconds": 450,
            "max_recovery_attempts": 3,
            "max_child_agents": 0,
        },
        can_create_children=False,
        max_children=0,
    ),
}


def get_role_definition(role: SubagentRole) -> RoleDefinition:
    """Get the definition for a role."""
    return DEFAULT_ROLES.get(role, RoleDefinition(
        role_id=role,
        description=f"Role: {role.value}",
    ))


def register_role(role: SubagentRole, definition: RoleDefinition) -> None:
    """Register or override a role definition."""
    DEFAULT_ROLES[role] = definition
