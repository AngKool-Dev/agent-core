"""Validation runner for ARGUS real-world scenarios."""

import time
from datetime import datetime
from typing import Dict, List, Optional

from argus.validation.contract import create_default_contract
from argus.validation.models import (
    ContractViolation,
    OutcomeType,
    ToolCallRecord,
    ValidationConfig,
    ValidationResult,
    ValidationRun,
    ValidationScenario,
    ValidationStatus,
)
from argus.validation.scenarios import get_all_scenarios, get_scenario_by_id
from argus.validation.verifier import ScenarioVerifier


class ValidationRunner:
    """Runs validation scenarios and collects results."""

    def __init__(
        self,
        config: Optional[ValidationConfig] = None,
        verifier: Optional[ScenarioVerifier] = None,
    ):
        self._config = config or ValidationConfig()
        self._verifier = verifier or ScenarioVerifier()
        self._contract = create_default_contract()

    def run_scenario(
        self,
        scenario: ValidationScenario,
        agent_callback=None,
    ) -> ValidationResult:
        """Run a single validation scenario."""
        result = ValidationResult(
            scenario_id=scenario.scenario_id,
            status=ValidationStatus.RUNNING,
            started_at=datetime.utcnow().isoformat(),
        )

        start_time = time.time()

        try:
            # Execute the scenario via agent callback
            if agent_callback:
                agent_result = agent_callback(scenario.prompt, scenario.initial_state)
                result.output = agent_result.get("output", "")
                result.tool_calls = [
                    ToolCallRecord(
                        tool_name=tc.get("tool", "unknown"),
                        arguments=tc.get("arguments", {}),
                        success=tc.get("success", True),
                        duration_ms=tc.get("duration_ms", 0.0),
                    )
                    for tc in agent_result.get("tool_calls", [])
                ]
                result.files_created = agent_result.get("files_created", [])
                result.files_modified = agent_result.get("files_modified", [])
                result.files_deleted = agent_result.get("files_deleted", [])
                result.errors = agent_result.get("errors", [])
                result.recovery_attempts = agent_result.get("recovery_attempts", 0)

            # Verify the result
            result = self._verifier.verify(scenario, result)

            # Enforce contract if enabled
            if self._config.enable_contract_enforcement:
                violations = self._contract.evaluate(result)
                result.contract_violations = violations
                if violations and any(
                    v in (
                        ContractViolation.OUTPUT_FORMAT,
                        ContractViolation.SAFETY_BOUNDARY,
                        ContractViolation.TIMEOUT,
                    )
                    for v in violations
                ):
                    result.success = False
                    if result.status == ValidationStatus.PASSED:
                        result.status = ValidationStatus.FAILED
                        result.outcome = OutcomeType.FAILURE

        except TimeoutError:
            result.status = ValidationStatus.TIMED_OUT
            result.outcome = OutcomeType.TIMEOUT
            result.success = False
            result.errors.append("Scenario timed out")
        except Exception as e:
            result.status = ValidationStatus.ERROR
            result.outcome = OutcomeType.ERROR
            result.success = False
            result.errors.append(str(e))

        result.duration_seconds = time.time() - start_time
        result.completed_at = datetime.utcnow().isoformat()

        return result

    def run_all(
        self,
        scenarios: Optional[List[ValidationScenario]] = None,
        agent_callback=None,
    ) -> ValidationRun:
        """Run all validation scenarios."""
        if scenarios is None:
            scenarios = get_all_scenarios()

        # Filter by config if specified
        if self._config.scenario_ids:
            scenarios = [s for s in scenarios if s.scenario_id in self._config.scenario_ids]

        run = ValidationRun(
            total_scenarios=len(scenarios),
            started_at=datetime.utcnow().isoformat(),
        )

        start_time = time.time()

        for scenario in scenarios:
            result = self.run_scenario(scenario, agent_callback)
            run.scenario_results[scenario.scenario_id] = result

            if result.status == ValidationStatus.PASSED:
                run.passed += 1
            elif result.status == ValidationStatus.FAILED:
                run.failed += 1
            elif result.status == ValidationStatus.ERROR:
                run.errors += 1
            elif result.status == ValidationStatus.SKIPPED:
                run.skipped += 1

        run.total_duration = time.time() - start_time
        run.completed_at = datetime.utcnow().isoformat()

        return run

    def run_by_tier(self, tier: str, agent_callback=None) -> ValidationRun:
        """Run scenarios for a specific tier."""
        scenarios = [s for s in get_all_scenarios() if s.tier.value == tier]
        return self.run_all(scenarios, agent_callback)

    def run_by_category(self, category: str, agent_callback=None) -> ValidationRun:
        """Run scenarios for a specific category."""
        scenarios = [s for s in get_all_scenarios() if s.category.value == category]
        return self.run_all(scenarios, agent_callback)


def run_validation(
    scenario_ids: Optional[List[str]] = None,
    agent_callback=None,
) -> ValidationRun:
    """Convenience function to run validation."""
    config = ValidationConfig(scenario_ids=scenario_ids)
    runner = ValidationRunner(config)
    return runner.run_all(agent_callback=agent_callback)


def run_single_scenario(
    scenario_id: str,
    agent_callback=None,
) -> Optional[ValidationResult]:
    """Run a single scenario by ID."""
    scenario = get_scenario_by_id(scenario_id)
    if not scenario:
        return None

    runner = ValidationRunner()
    return runner.run_scenario(scenario, agent_callback)
