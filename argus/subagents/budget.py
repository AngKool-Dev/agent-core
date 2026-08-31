"""Subagent budget system for ARGUS."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from argus.subagents.models import SubagentRole
from argus.subagents.roles import get_role_definition


@dataclass
class SubagentBudget:
    """Finite budget for a subagent."""
    max_model_calls: int = 20
    max_tool_calls: int = 30
    max_iterations: int = 10
    max_time_seconds: int = 300
    max_tokens: int = 50000
    max_recovery_attempts: int = 2
    max_child_agents: int = 0

    # Usage tracking
    model_calls: int = 0
    tool_calls: int = 0
    iterations: int = 0
    tokens_used: int = 0
    recovery_attempts: int = 0
    child_agents_created: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def remaining_model_calls(self) -> int:
        return max(0, self.max_model_calls - self.model_calls)

    @property
    def remaining_tool_calls(self) -> int:
        return max(0, self.max_tool_calls - self.tool_calls)

    @property
    def remaining_iterations(self) -> int:
        return max(0, self.max_iterations - self.iterations)

    @property
    def remaining_time(self) -> float:
        elapsed = time.time() - self.start_time
        return max(0, self.max_time_seconds - elapsed)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.tokens_used)

    @property
    def remaining_recovery_attempts(self) -> int:
        return max(0, self.max_recovery_attempts - self.recovery_attempts)

    @property
    def remaining_child_agents(self) -> int:
        return max(0, self.max_child_agents - self.child_agents_created)

    def consume_model_call(self, tokens: int = 0) -> bool:
        """Consume a model call. Returns False if budget exhausted."""
        if self.model_calls >= self.max_model_calls:
            return False
        self.model_calls += 1
        self.tokens_used += tokens
        return True

    def consume_tool_call(self) -> bool:
        """Consume a tool call. Returns False if budget exhausted."""
        if self.tool_calls >= self.max_tool_calls:
            return False
        self.tool_calls += 1
        return True

    def consume_iteration(self) -> bool:
        """Consume an iteration. Returns False if budget exhausted."""
        if self.iterations >= self.max_iterations:
            return False
        self.iterations += 1
        return True

    def consume_recovery(self) -> bool:
        """Consume a recovery attempt. Returns False if budget exhausted."""
        if self.recovery_attempts >= self.max_recovery_attempts:
            return False
        self.recovery_attempts += 1
        return True

    def create_child(self) -> bool:
        """Create a child agent. Returns False if budget exhausted."""
        if self.child_agents_created >= self.max_child_agents:
            return False
        self.child_agents_created += 1
        return True

    @property
    def is_exhausted(self) -> bool:
        """Check if any budget is exhausted."""
        return (
            self.model_calls >= self.max_model_calls
            or self.tool_calls >= self.max_tool_calls
            or self.iterations >= self.max_iterations
            or self.remaining_time <= 0
            or self.tokens_used >= self.max_tokens
        )

    @property
    def exhausted_reason(self) -> Optional[str]:
        """Get the reason for budget exhaustion."""
        if self.model_calls >= self.max_model_calls:
            return "max_model_calls exhausted"
        if self.tool_calls >= self.max_tool_calls:
            return "max_tool_calls exhausted"
        if self.iterations >= self.max_iterations:
            return "max_iterations exhausted"
        if self.remaining_time <= 0:
            return "max_time exhausted"
        if self.tokens_used >= self.max_tokens:
            return "max_tokens exhausted"
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_iterations": self.max_iterations,
            "max_time_seconds": self.max_time_seconds,
            "max_tokens": self.max_tokens,
            "max_recovery_attempts": self.max_recovery_attempts,
            "max_child_agents": self.max_child_agents,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "iterations": self.iterations,
            "tokens_used": self.tokens_used,
            "recovery_attempts": self.recovery_attempts,
            "child_agents_created": self.child_agents_created,
        }

    def usage_summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return {
            "model_calls": f"{self.model_calls}/{self.max_model_calls}",
            "tool_calls": f"{self.tool_calls}/{self.max_tool_calls}",
            "iterations": f"{self.iterations}/{self.max_iterations}",
            "time": f"{self.max_time_seconds - self.remaining_time:.0f}/{self.max_time_seconds}s",
            "recovery": f"{self.recovery_attempts}/{self.max_recovery_attempts}",
            "children": f"{self.child_agents_created}/{self.max_child_agents}",
        }


def create_budget(
    role: SubagentRole,
    overrides: Optional[Dict[str, int]] = None,
) -> SubagentBudget:
    """Create a budget for a role with optional overrides."""
    role_def = get_role_definition(role)
    limits = role_def.default_limits

    # Apply overrides
    if overrides:
        limits.update(overrides)

    return SubagentBudget(
        max_model_calls=limits.get("max_model_calls", 20),
        max_tool_calls=limits.get("max_tool_calls", 30),
        max_iterations=limits.get("max_iterations", 10),
        max_time_seconds=limits.get("max_time_seconds", 300),
        max_tokens=limits.get("max_tokens", 50000),
        max_recovery_attempts=limits.get("max_recovery_attempts", 2),
        max_child_agents=limits.get("max_child_agents", 0),
    )


def derive_child_budget(
    parent_budget: SubagentBudget,
    role: SubagentRole,
) -> SubagentBudget:
    """Derive a child budget from parent's remaining budget."""
    role_def = get_role_definition(role)
    limits = role_def.default_limits

    # Child budget is a subset of parent's remaining budget
    return SubagentBudget(
        max_model_calls=min(limits.get("max_model_calls", 20), parent_budget.remaining_model_calls),
        max_tool_calls=min(limits.get("max_tool_calls", 30), parent_budget.remaining_tool_calls),
        max_iterations=min(limits.get("max_iterations", 10), parent_budget.remaining_iterations),
        max_time_seconds=min(limits.get("max_time_seconds", 300), int(parent_budget.remaining_time)),
        max_tokens=min(limits.get("max_tokens", 50000), parent_budget.remaining_tokens),
        max_recovery_attempts=min(limits.get("max_recovery_attempts", 2), parent_budget.remaining_recovery_attempts),
        max_child_agents=0,  # Children cannot create children by default
    )
