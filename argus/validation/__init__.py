"""ARGUS Validation - Real-world agent validation scenarios and framework.

This package provides real-world validation scenarios for testing ARGUS agent
capabilities, including the Real Agent Outcome Contract for defining what
"done" means for agent tasks.
"""

from argus.validation.models import (
    ContractClause,
    ContractViolation,
    OutcomeContract,
    OutcomeType,
    ToolCallRecord,
    ValidationCategory,
    ValidationConfig,
    ValidationConstraint,
    ValidationResult,
    ValidationRun,
    ValidationScenario,
    ValidationStatus,
    ValidationTier,
)
from argus.validation.scenarios import (
    get_all_scenarios,
    get_scenario_by_id,
    get_scenarios_by_category,
    get_scenarios_by_tier,
    scenario_a_file_creation,
    scenario_b_debugging,
    scenario_c_refactoring,
    scenario_d_testing,
    scenario_e_git_workflow,
    scenario_f_dependency_management,
    scenario_g_security_review,
    scenario_h_multi_step_reasoning,
    scenario_i_documentation,
    scenario_j_recovery_task,
)
from argus.validation.contract import (
    create_default_contract,
    create_lenient_contract,
    create_strict_contract,
)
from argus.validation.verifier import ScenarioVerifier
from argus.validation.runner import (
    ValidationRunner,
    run_validation,
    run_single_scenario,
)
from argus.validation.evaluator import (
    ValidationEvaluator,
    evaluate_validation_run,
)
from argus.validation.reporter import (
    ValidationReporter,
    generate_validation_report,
)

__all__ = [
    # Models
    "ContractClause",
    "ContractViolation",
    "OutcomeContract",
    "OutcomeType",
    "ToolCallRecord",
    "ValidationCategory",
    "ValidationConfig",
    "ValidationConstraint",
    "ValidationResult",
    "ValidationRun",
    "ValidationScenario",
    "ValidationStatus",
    "ValidationTier",
    # Scenarios
    "get_all_scenarios",
    "get_scenario_by_id",
    "get_scenarios_by_category",
    "get_scenarios_by_tier",
    "scenario_a_file_creation",
    "scenario_b_debugging",
    "scenario_c_refactoring",
    "scenario_d_testing",
    "scenario_e_git_workflow",
    "scenario_f_dependency_management",
    "scenario_g_security_review",
    "scenario_h_multi_step_reasoning",
    "scenario_i_documentation",
    "scenario_j_recovery_task",
    # Contract
    "create_default_contract",
    "create_lenient_contract",
    "create_strict_contract",
    # Verifier
    "ScenarioVerifier",
    # Runner
    "ValidationRunner",
    "run_validation",
    "run_single_scenario",
    # Evaluator
    "ValidationEvaluator",
    "evaluate_validation_run",
    # Reporter
    "ValidationReporter",
    "generate_validation_report",
]
