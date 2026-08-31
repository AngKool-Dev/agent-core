"""Subagent task management for ARGUS."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from argus.subagents.models import SubagentRole


@dataclass
class TaskTemplate:
    """Template for creating subagent tasks."""
    name: str
    role: SubagentRole
    description: str
    default_objective: str = ""
    default_constraints: Dict[str, Any] = field(default_factory=dict)
    default_inputs: Dict[str, Any] = field(default_factory=dict)
    required_output: Dict[str, Any] = field(default_factory=dict)

    def create_task(
        self,
        objective: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        parent_run_id: str = "",
        parent_task_id: str = "",
    ) -> Dict[str, Any]:
        """Create a task from this template."""
        return {
            "objective": objective or self.default_objective,
            "role": self.role.value,
            "inputs": {**self.default_inputs, **(inputs or {})},
            "constraints": {**self.default_constraints, **(constraints or {})},
            "required_output": self.required_output,
            "parent_run_id": parent_run_id,
            "parent_task_id": parent_task_id,
        }


# Default task templates
DEFAULT_TEMPLATES: Dict[str, TaskTemplate] = {
    "research": TaskTemplate(
        name="research",
        role=SubagentRole.RESEARCHER,
        description="Research and gather evidence",
        default_objective="Research the given topic and provide evidence-based findings",
        default_constraints={
            "termination_conditions": ["sufficient_evidence"],
        },
        required_output={
            "findings": "list of findings with evidence",
            "confidence": "confidence level (0-1)",
        },
    ),

    "implement": TaskTemplate(
        name="implement",
        role=SubagentRole.IMPLEMENTER,
        description="Implement code changes",
        default_objective="Implement the requested changes",
        default_constraints={
            "termination_conditions": ["implementation_complete"],
        },
        required_output={
            "files_changed": "list of changed files",
            "description": "description of changes",
        },
    ),

    "test": TaskTemplate(
        name="test",
        role=SubagentRole.TESTER,
        description="Run tests and validate behavior",
        default_objective="Run tests and validate the implementation",
        default_constraints={
            "termination_conditions": ["tests_complete"],
        },
        required_output={
            "tests_passed": "number of tests passed",
            "tests_failed": "number of tests failed",
            "coverage": "test coverage if available",
        },
    ),

    "review": TaskTemplate(
        name="review",
        role=SubagentRole.REVIEWER,
        description="Review code and provide feedback",
        default_objective="Review the implementation and provide evidence-based feedback",
        default_constraints={
            "termination_conditions": ["review_complete"],
        },
        required_output={
            "findings": "list of review findings",
            "recommendations": "list of recommendations",
        },
    ),

    "debug": TaskTemplate(
        name="debug",
        role=SubagentRole.DEBUGGER,
        description="Diagnose and fix bugs",
        default_objective="Diagnose the issue and implement a fix",
        default_constraints={
            "termination_conditions": ["issue_resolved"],
        },
        required_output={
            "root_cause": "identified root cause",
            "fix_description": "description of the fix",
            "verification": "verification that the fix works",
        },
    ),
}


def get_template(name: str) -> Optional[TaskTemplate]:
    """Get a task template by name."""
    return DEFAULT_TEMPLATES.get(name)


def register_template(name: str, template: TaskTemplate) -> None:
    """Register a task template."""
    DEFAULT_TEMPLATES[name] = template


def list_templates() -> List[str]:
    """List available task templates."""
    return list(DEFAULT_TEMPLATES.keys())
