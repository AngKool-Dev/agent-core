"""Subagent context isolation for ARGUS."""

from typing import Any, Dict, List, Optional

from argus.subagents.models import SubagentRole


class SubagentContext:
    """Isolated context for a subagent."""

    def __init__(
        self,
        objective: str,
        role: SubagentRole,
        inputs: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ):
        self._objective = objective
        self._role = role
        self._inputs = inputs or {}
        self._constraints = constraints or {}
        self._working_memory: Dict[str, Any] = {}

    @property
    def objective(self) -> str:
        return self._objective

    @property
    def role(self) -> SubagentRole:
        return self._role

    @property
    def inputs(self) -> Dict[str, Any]:
        return dict(self._inputs)

    def get_input(self, key: str, default: Any = None) -> Any:
        """Get an input value."""
        return self._inputs.get(key, default)

    def set_working_memory(self, key: str, value: Any) -> None:
        """Set working memory (scoped to this subagent)."""
        self._working_memory[key] = value

    def get_working_memory(self, key: str, default: Any = None) -> Any:
        """Get working memory."""
        return self._working_memory.get(key, default)

    @property
    def working_memory(self) -> Dict[str, Any]:
        """Get all working memory."""
        return dict(self._working_memory)

    def build_prompt_context(self) -> Dict[str, Any]:
        """Build context for model prompt."""
        return {
            "objective": self._objective,
            "role": self._role.value,
            "inputs": self._inputs,
            "constraints": self._constraints,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self._objective,
            "role": self._role.value,
            "inputs": self._inputs,
            "constraints": self._constraints,
        }


def create_context(
    objective: str,
    role: SubagentRole,
    inputs: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> SubagentContext:
    """Create a subagent context."""
    return SubagentContext(
        objective=objective,
        role=role,
        inputs=inputs,
        constraints=constraints,
    )
