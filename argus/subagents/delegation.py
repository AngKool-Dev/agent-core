"""Delegation contract for ARGUS subagents."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.subagents.models import SubagentRole


@dataclass(frozen=True)
class DelegationContract:
    """Contract governing a subagent's operation."""
    contract_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    objective: str = ""

    # Scopes
    allowed_capabilities: List[str] = field(default_factory=list)
    denied_capabilities: List[str] = field(default_factory=list)
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    allowed_commands: List[str] = field(default_factory=list)
    denied_commands: List[str] = field(default_factory=list)
    allowed_network: List[str] = field(default_factory=list)

    # Limits
    max_iterations: int = 10
    max_time_seconds: int = 300
    max_model_calls: int = 20
    max_tool_calls: int = 30
    max_tokens: int = 50000
    max_recovery_attempts: int = 2
    max_child_agents: int = 0

    # Output
    output_schema: Dict[str, Any] = field(default_factory=dict)
    termination_conditions: List[str] = field(default_factory=list)

    # Metadata
    created_at: float = field(default_factory=time.time)
    role: SubagentRole = SubagentRole.RESEARCHER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "objective": self.objective,
            "allowed_capabilities": self.allowed_capabilities,
            "denied_capabilities": self.denied_capabilities,
            "allowed_paths": self.allowed_paths,
            "denied_paths": self.denied_paths,
            "allowed_commands": self.allowed_commands,
            "denied_commands": self.denied_commands,
            "allowed_network": self.allowed_network,
            "max_iterations": self.max_iterations,
            "max_time_seconds": self.max_time_seconds,
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_tokens": self.max_tokens,
            "max_recovery_attempts": self.max_recovery_attempts,
            "max_child_agents": self.max_child_agents,
            "output_schema": self.output_schema,
            "termination_conditions": self.termination_conditions,
            "created_at": self.created_at,
            "role": self.role.value,
        }


def create_contract(
    objective: str,
    role: SubagentRole,
    overrides: Optional[Dict[str, Any]] = None,
) -> DelegationContract:
    """Create a delegation contract from role defaults."""
    from argus.subagents.roles import get_role_definition

    role_def = get_role_definition(role)
    limits = role_def.default_limits

    contract = DelegationContract(
        objective=objective,
        allowed_capabilities=list(role_def.default_capabilities),
        denied_capabilities=list(role_def.denied_capabilities),
        allowed_commands=list(role_def.allowed_operations),
        denied_commands=list(role_def.denied_operations),
        max_iterations=limits.get("max_iterations", 10),
        max_time_seconds=limits.get("max_time_seconds", 300),
        max_model_calls=limits.get("max_model_calls", 20),
        max_tool_calls=limits.get("max_tool_calls", 30),
        max_tokens=limits.get("max_tokens", 50000),
        max_recovery_attempts=limits.get("max_recovery_attempts", 2),
        max_child_agents=role_def.max_children,
        role=role,
    )

    if overrides:
        # Apply overrides
        for key, value in overrides.items():
            if hasattr(contract, key):
                object.__setattr__(contract, key, value)

    return contract
