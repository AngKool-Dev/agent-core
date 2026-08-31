"""ARGUS Subagents + Controlled Delegation."""

from argus.subagents.aggregation import AggregationResult, ResultAggregator
from argus.subagents.budget import SubagentBudget, create_budget, derive_child_budget
from argus.subagents.context import SubagentContext, create_context
from argus.subagents.delegation import DelegationContract, create_contract
from argus.subagents.executor import SubagentExecutor
from argus.subagents.lifecycle import LifecycleManager, PolicyEnforcer, get_policy, set_policy
from argus.subagents.manager import SubagentManager
from argus.subagents.models import (
    Subagent,
    SubagentId,
    SubagentResult,
    SubagentRole,
    SubagentStatus,
    SubagentTask,
    is_valid_transition,
)
from argus.subagents.orchestrator import SubagentOrchestrator, create_orchestrator
from argus.subagents.report import format_subagents_text
from argus.subagents.result import ResultFormatter, summarize_results
from argus.subagents.roles import RoleDefinition, get_role_definition, register_role
from argus.subagents.task import TaskTemplate, get_template, list_templates, register_template

__all__ = [
    # Aggregation
    "AggregationResult",
    "ResultAggregator",
    # Budget
    "SubagentBudget",
    "create_budget",
    "derive_child_budget",
    # Context
    "SubagentContext",
    "create_context",
    # Delegation
    "DelegationContract",
    "create_contract",
    # Executor
    "SubagentExecutor",
    # Lifecycle
    "LifecycleManager",
    "PolicyEnforcer",
    "get_policy",
    "set_policy",
    # Manager
    "SubagentManager",
    # Models
    "Subagent",
    "SubagentId",
    "SubagentResult",
    "SubagentRole",
    "SubagentStatus",
    "SubagentTask",
    "is_valid_transition",
    # Orchestrator
    "SubagentOrchestrator",
    "create_orchestrator",
    # Report
    "format_subagents_text",
    # Result
    "ResultFormatter",
    "summarize_results",
    # Roles
    "RoleDefinition",
    "get_role_definition",
    "register_role",
    # Task
    "TaskTemplate",
    "get_template",
    "list_templates",
    "register_template",
]
