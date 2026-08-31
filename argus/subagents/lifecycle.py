"""Subagent lifecycle management for ARGUS."""

import time
from typing import Any, Callable, Dict, List, Optional

from argus.subagents.models import (
    Subagent,
    SubagentId,
    SubagentResult,
    SubagentRole,
    SubagentStatus,
)


class LifecycleManager:
    """Manages subagent lifecycle transitions."""

    def __init__(self):
        self._transitions: List[Dict[str, Any]] = []

    def record_transition(
        self,
        subagent_id: str,
        from_status: SubagentStatus,
        to_status: SubagentStatus,
        reason: str = "",
    ) -> None:
        """Record a lifecycle transition."""
        self._transitions.append({
            "subagent_id": subagent_id,
            "from_status": from_status.value,
            "to_status": to_status.value,
            "reason": reason,
            "timestamp": time.time(),
        })

    def get_transitions(self, subagent_id: str) -> List[Dict[str, Any]]:
        """Get transitions for a subagent."""
        return [t for t in self._transitions if t["subagent_id"] == subagent_id]

    def get_all_transitions(self) -> List[Dict[str, Any]]:
        """Get all transitions."""
        return list(self._transitions)

    def clear(self) -> None:
        """Clear all transitions."""
        self._transitions.clear()


class PolicyEnforcer:
    """Enforces policies on subagent operations."""

    def __init__(
        self,
        max_concurrent: int = 3,
        max_depth: int = 1,
        default_max_children: int = 0,
    ):
        self._max_concurrent = max_concurrent
        self._max_depth = max_depth
        self._default_max_children = default_max_children

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def max_depth(self) -> int:
        return self._max_depth

    def can_create_child(
        self,
        parent: Subagent,
        current_depth: int,
    ) -> bool:
        """Check if a child can be created."""
        # Check depth limit
        if current_depth >= self._max_depth:
            return False

        # Check parent's child limit
        if len(parent.child_ids) >= parent.budget.get("max_child_agents", self._default_max_children):
            return False

        return True

    def can_execute_concurrent(self, active_count: int) -> bool:
        """Check if a new subagent can execute concurrently."""
        return active_count < self._max_concurrent

    def validate_capability(
        self,
        subagent: Subagent,
        capability: str,
    ) -> bool:
        """Validate if a subagent can use a capability."""
        # Check capability scope
        if subagent.capability_scope:
            if capability not in subagent.capability_scope:
                return False

        return True

    def validate_path(
        self,
        subagent: Subagent,
        path: str,
    ) -> bool:
        """Validate if a subagent can access a path."""
        # Check denied paths
        for denied in subagent.path_scope:
            if denied.startswith("!"):
                denied_path = denied[1:]
                if path.startswith(denied_path):
                    return False

        return True

    def validate_command(
        self,
        subagent: Subagent,
        command: str,
    ) -> bool:
        """Validate if a subagent can execute a command."""
        # Check denied commands
        for denied in subagent.command_scope:
            if denied.startswith("!"):
                denied_cmd = denied[1:]
                if denied_cmd in command:
                    return False

        return True


# Global policy enforcer
_default_policy = PolicyEnforcer()


def get_policy() -> PolicyEnforcer:
    """Get the global policy enforcer."""
    return _default_policy


def set_policy(policy: PolicyEnforcer) -> None:
    """Set the global policy enforcer."""
    global _default_policy
    _default_policy = policy
