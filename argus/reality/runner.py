"""Reality validation runner for ARGUS qualification."""

import time
from datetime import datetime
from typing import Dict, Optional

from argus.reality.environment import ProductionEnvironment
from argus.reality.invariants import InvariantTester
from argus.reality.mcp import RealMCPValidator
from argus.reality.models import (
    RealityRun,
    RealityStatus,
)
from argus.reality.providers import RealProviderValidator
from argus.reality.scenarios import RealityScenarioRunner
from argus.reality.secrets import SecretSafetyAuditor
from argus.reality.subprocesses import SubprocessRealityTester
from argus.reality.windows import WindowsHardeningTester


class RealityRunner:
    """Runs the complete reality validation suite."""

    def __init__(self):
        self._environment = ProductionEnvironment()
        self._run: Optional[RealityRun] = None

    def run_all(self) -> RealityRun:
        """Run all reality validation checks."""
        self._run = RealityRun(
            started_at=datetime.utcnow().isoformat(),
        )

        start_time = time.time()

        # Capture environment
        self._run.environment = self._environment.snapshot()

        # Run provider validation
        self._run_provider_tests()

        # Run MCP validation
        self._run_mcp_tests()

        # Run subprocess tests
        self._run_subprocess_tests()

        # Run Windows tests
        self._run_windows_tests()

        # Run secret safety audit
        self._run_secret_audit()

        # Run invariant tests
        self._run_invariant_tests()

        # Run scenario tests
        self._run_scenario_tests()

        # Calculate totals
        self._run.total_duration = time.time() - start_time
        self._run.completed_at = datetime.utcnow().isoformat()
        self._calculate_totals()

        return self._run

    def _run_provider_tests(self):
        """Run provider validation tests."""
        validator = RealProviderValidator(self._run.environment)
        results = validator.validate_all()
        self._run.provider_results = results

    def _run_mcp_tests(self):
        """Run MCP validation tests."""
        validator = RealMCPValidator()
        results = validator.validate_all()
        self._run.mcp_results = results

    def _run_subprocess_tests(self):
        """Run subprocess reality tests."""
        tester = SubprocessRealityTester()
        results = tester.run_all_tests()
        self._run.subprocess_results = results

    def _run_windows_tests(self):
        """Run Windows hardening tests."""
        tester = WindowsHardeningTester()
        results = tester.run_all_tests()
        self._run.windows_results = results

    def _run_secret_audit(self):
        """Run secret safety audit."""
        auditor = SecretSafetyAuditor()
        results = auditor.run_full_audit()
        self._run.secret_canary_results = results

    def _run_invariant_tests(self):
        """Run invariant tests."""
        tester = InvariantTester()
        results = tester.run_all_tests()
        self._run.invariant_results = results

    def _run_scenario_tests(self):
        """Run end-to-end scenario tests."""
        runner = RealityScenarioRunner(self._run.environment)
        results = runner.run_all_scenarios()
        self._run.scenario_results = results

    def _calculate_totals(self):
        """Calculate total check counts."""
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        inconclusive = 0
        infrastructure_failures = 0

        # Count all results
        all_results = [
            self._run.provider_results,
            self._run.mcp_results,
            self._run.subprocess_results,
            self._run.windows_results,
            self._run.secret_canary_results,
            self._run.invariant_results,
            self._run.scenario_results,
        ]

        for result_dict in all_results:
            for key, result in result_dict.items():
                total += 1
                status = getattr(result, "status", None)
                if status == RealityStatus.PASSED:
                    passed += 1
                elif status == RealityStatus.FAILED:
                    failed += 1
                elif status == RealityStatus.SKIPPED:
                    skipped += 1
                elif status == RealityStatus.INCONCLUSIVE:
                    inconclusive += 1
                elif status == RealityStatus.INFRASTRUCTURE_FAILURE:
                    infrastructure_failures += 1

        self._run.total_checks = total
        self._run.passed = passed
        self._run.failed = failed
        self._run.skipped = skipped
        self._run.inconclusive = inconclusive
        self._run.infrastructure_failures = infrastructure_failures

    @property
    def run(self) -> Optional[RealityRun]:
        """Get the current run."""
        return self._run


def run_reality_suite() -> RealityRun:
    """Convenience function to run the complete reality suite."""
    runner = RealityRunner()
    return runner.run_all()
