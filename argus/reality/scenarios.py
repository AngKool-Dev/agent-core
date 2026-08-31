"""End-to-end reality scenarios for ARGUS qualification."""

import time
from datetime import datetime
from typing import Dict, List, Optional

from argus.reality.models import (
    EnvironmentInfo,
    FailureCategory,
    RealityScenarioResult,
    RealityStatus,
)
from argus.validation.scenarios import get_all_scenarios, ValidationScenario


class RealityScenarioRunner:
    """Runs end-to-end reality scenarios through the actual ARGUS stack."""

    def __init__(self, environment: Optional[EnvironmentInfo] = None):
        self._environment = environment
        self._results: Dict[str, RealityScenarioResult] = {}

    def run_all_scenarios(self) -> Dict[str, RealityScenarioResult]:
        """Run all validation scenarios through the real stack."""
        scenarios = get_all_scenarios()

        for scenario in scenarios:
            result = self._run_scenario(scenario)
            self._results[scenario.scenario_id] = result

        return self._results

    def run_scenario(self, scenario_id: str) -> Optional[RealityScenarioResult]:
        """Run a single scenario by ID."""
        from argus.validation.scenarios import get_scenario_by_id
        scenario = get_scenario_by_id(scenario_id)
        if not scenario:
            return None

        result = self._run_scenario(scenario)
        self._results[scenario_id] = result
        return result

    def _run_scenario(self, scenario: ValidationScenario) -> RealityScenarioResult:
        """Run a single scenario through the real ARGUS stack."""
        start_time = time.time()

        result = RealityScenarioResult(
            scenario_id=scenario.scenario_id,
            status=RealityStatus.RUNNING,
            environment=self._environment,
        )

        try:
            # Reset event bus for clean measurement
            from argus.events import reset_event_bus, get_event_bus
            reset_event_bus()
            bus = get_event_bus()

            # Count events
            from argus.events import MemorySink
            sink = MemorySink()
            bus.subscribe(sink.emit)

            # Create agent configuration
            from argus.config import ArgusConfig
            config = ArgusConfig()

            # Create model
            from argus.model import create_model_from_config
            model_config = {
                "provider": config.get("model.provider", "ollama"),
                "name": config.get("model.name", "llama3"),
            }
            model = create_model_from_config(model_config)

            if model is None:
                result.status = RealityStatus.INCONCLUSIVE
                result.failure_category = FailureCategory.INFRASTRUCTURE_FAILURE
                result.error_message = "Could not create model - provider unavailable"
                return result

            result.provider_used = model_config["provider"]

            # Create agent
            from argus.agent import ArgusAgent
            from pathlib import Path
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                agent = ArgusAgent(
                    project_path=Path(tmpdir),
                    config=config,
                    model=model,
                )

                # Execute the scenario
                agent_result = agent.execute(scenario.prompt)

                # Capture results
                result.events_emitted = sink.event_count
                result.tool_calls = agent_result.get("tool_calls", 0)
                result.verification_passed = agent_result.get("verification_passed", False)
                result.recovery_attempts = agent_result.get("recovery_attempts", 0)
                result.review_passed = agent_result.get("review_passed", False)

                # Determine outcome
                if agent_result.get("success"):
                    result.status = RealityStatus.PASSED
                elif agent_result.get("inconclusive"):
                    result.status = RealityStatus.INCONCLUSIVE
                    result.failure_category = FailureCategory.INFRASTRUCTURE_FAILURE
                else:
                    result.status = RealityStatus.FAILED
                    result.failure_category = FailureCategory.AGENT_FAILURE

        except Exception as e:
            result.status = RealityStatus.ERROR
            result.failure_category = FailureCategory.INFRASTRUCTURE_FAILURE
            result.error_message = str(e)

        result.duration_seconds = time.time() - start_time
        return result

    @property
    def results(self) -> Dict[str, RealityScenarioResult]:
        """Get all scenario results."""
        return self._results


def run_reality_scenarios() -> Dict[str, RealityScenarioResult]:
    """Convenience function to run all reality scenarios."""
    runner = RealityScenarioRunner()
    return runner.run_all_scenarios()
