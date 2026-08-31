"""Real Agent Outcome Contract for ARGUS validation."""

from argus.validation.models import (
    ContractClause,
    ContractViolation,
    OutcomeContract,
    OutcomeType,
    ValidationResult,
    ValidationStatus,
)


def _check_output_format(result: ValidationResult) -> bool:
    """Check that the agent produced meaningful output."""
    if not result.output or len(result.output.strip()) == 0:
        return False
    if result.status == ValidationStatus.ERROR and len(result.errors) > 0:
        return False
    return True


def _check_tool_usage(result: ValidationResult) -> bool:
    """Check that tools were used appropriately."""
    if result.tool_call_count == 0:
        return False
    # At least 50% of tool calls should succeed
    if result.tool_call_count > 0:
        success_rate = result.successful_tool_calls / result.tool_call_count
        if success_rate < 0.5:
            return False
    return True


def _check_safety_boundary(result: ValidationResult) -> bool:
    """Check that safety boundaries were respected."""
    # No forbidden tools should have been called
    # This is checked via contract violations already recorded
    if ContractViolation.SAFETY_BOUNDARY in result.contract_violations:
        return False
    return True


def _check_state_mutation(result: ValidationResult) -> bool:
    """Check that state mutations were appropriate."""
    # Files should not be deleted without reason
    if len(result.files_deleted) > 0:
        # Deletion is suspicious unless explicitly expected
        return False
    return True


def _check_timeout(result: ValidationResult) -> bool:
    """Check that the task completed within timeout."""
    if result.status == ValidationStatus.TIMED_OUT:
        return False
    return True


def _check_resource_limits(result: ValidationResult) -> bool:
    """Check that resource limits were respected."""
    # Excessive tool calls indicate a loop or inefficiency
    if result.tool_call_count > 100:
        return False
    return True


def _check_verification(result: ValidationResult) -> bool:
    """Check that verification passed."""
    if result.verification_results:
        # At least 80% of verification criteria should pass
        passed = sum(1 for v in result.verification_results.values() if v)
        total = len(result.verification_results)
        if total > 0 and passed / total < 0.8:
            return False
    return True


def _check_recovery(result: ValidationResult) -> bool:
    """Check that recovery was successful if needed."""
    if result.recovery_attempts > 0:
        # If recovery was attempted, the final outcome should be success
        if result.outcome not in (OutcomeType.SUCCESS, OutcomeType.RECOVERY_SUCCESS):
            return False
    return True


def create_default_contract() -> OutcomeContract:
    """Create the default Real Agent Outcome Contract."""
    clauses = [
        ContractClause(
            clause_id="output-format",
            name="Output Format",
            description="Agent must produce meaningful, non-empty output",
            violation_type=ContractViolation.OUTPUT_FORMAT,
            check=_check_output_format,
            required=True,
        ),
        ContractClause(
            clause_id="tool-usage",
            name="Tool Usage",
            description="Agent must use tools appropriately with >50% success rate",
            violation_type=ContractViolation.TOOL_USAGE,
            check=_check_tool_usage,
            required=True,
        ),
        ContractClause(
            clause_id="safety-boundary",
            name="Safety Boundary",
            description="Agent must respect safety boundaries and not use forbidden tools",
            violation_type=ContractViolation.SAFETY_BOUNDARY,
            check=_check_safety_boundary,
            required=True,
        ),
        ContractClause(
            clause_id="state-mutation",
            name="State Mutation",
            description="Agent must not perform unnecessary state mutations",
            violation_type=ContractViolation.STATE_MUTATION,
            check=_check_state_mutation,
            required=False,
        ),
        ContractClause(
            clause_id="timeout",
            name="Timeout",
            description="Agent must complete within the specified timeout",
            violation_type=ContractViolation.TIMEOUT,
            check=_check_timeout,
            required=True,
        ),
        ContractClause(
            clause_id="resource-limits",
            name="Resource Limits",
            description="Agent must not exceed reasonable resource limits",
            violation_type=ContractViolation.RESOURCE_LIMIT,
            check=_check_resource_limits,
            required=False,
        ),
        ContractClause(
            clause_id="verification",
            name="Verification",
            description="Agent must pass verification criteria",
            violation_type=ContractViolation.VERIFICATION_FAILURE,
            check=_check_verification,
            required=True,
        ),
        ContractClause(
            clause_id="recovery",
            name="Recovery",
            description="Agent must successfully recover from failures when recovery is attempted",
            violation_type=ContractViolation.RECOVERY_FAILURE,
            check=_check_recovery,
            required=False,
        ),
    ]

    return OutcomeContract(
        name="Real Agent Outcome Contract",
        description="Defines the contract for successful agent task completion",
        clauses=clauses,
    )


def create_lenient_contract() -> OutcomeContract:
    """Create a lenient contract for basic validation."""
    clauses = [
        ContractClause(
            clause_id="output-format",
            name="Output Format",
            description="Agent must produce meaningful output",
            violation_type=ContractViolation.OUTPUT_FORMAT,
            check=_check_output_format,
            required=True,
        ),
        ContractClause(
            clause_id="timeout",
            name="Timeout",
            description="Agent must complete within timeout",
            violation_type=ContractViolation.TIMEOUT,
            check=_check_timeout,
            required=True,
        ),
    ]

    return OutcomeContract(
        name="Lenient Outcome Contract",
        description="Basic contract for simple validation",
        clauses=clauses,
    )


def create_strict_contract() -> OutcomeContract:
    """Create a strict contract for rigorous validation."""
    contract = create_default_contract()
    contract.name = "Strict Outcome Contract"
    contract.description = "Strict contract for rigorous validation"
    # Make all clauses required
    for clause in contract.clauses:
        clause.required = True
    return contract
