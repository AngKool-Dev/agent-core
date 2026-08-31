"""Release qualification runner for ARGUS."""

import time
from datetime import datetime
from typing import Dict, Optional

from argus.release.artifacts import validate_all_artifacts
from argus.release.cleanroom import test_clean_installation
from argus.release.invariants import ReleaseInvariantTester
from argus.release.metadata import check_version_consistency
from argus.release.models import (
    ArtifactStatus,
    ConcurrencyResult,
    ContaminationScanResult,
    ReleaseRun,
    SmokeTestResult,
    StabilityResult,
)


class ReleaseRunner:
    """Runs the complete release qualification suite."""

    def __init__(self, dist_dir: str = "dist"):
        self._dist_dir = dist_dir
        self._run: Optional[ReleaseRun] = None

    def run_all(self) -> ReleaseRun:
        """Run all release qualification checks."""
        self._run = ReleaseRun(
            started_at=datetime.utcnow().isoformat(),
        )

        start_time = time.time()

        # Validate artifacts
        self._run_artifact_validation()

        # Check version consistency
        self._run_version_check()

        # Run invariant tests
        self._run_invariants()

        # Calculate totals
        self._run.total_duration = time.time() - start_time
        self._run.completed_at = datetime.utcnow().isoformat()
        self._calculate_totals()

        return self._run

    def _run_artifact_validation(self):
        """Run artifact validation."""
        results = validate_all_artifacts(self._dist_dir)
        self._run.artifact_results = results

    def _run_version_check(self):
        """Run version consistency check."""
        self._run.version_info = check_version_consistency()

    def _run_invariants(self):
        """Run release invariant tests."""
        tester = ReleaseInvariantTester()
        self._run.invariant_results = tester.run_all_tests()

    def _calculate_totals(self):
        """Calculate total check counts."""
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        inconclusive = 0

        # Count artifact results
        for result in self._run.artifact_results.values():
            total += 1
            if result.status == ArtifactStatus.VALID:
                passed += 1
            elif result.status == ArtifactStatus.INVALID:
                failed += 1
            elif result.status == ArtifactStatus.ERROR:
                failed += 1

        # Count invariant results
        for result in self._run.invariant_results.values():
            total += 1
            if result.status.value == "pass":
                passed += 1
            elif result.status.value == "fail":
                failed += 1
            elif result.status.value == "skipped":
                skipped += 1
            elif result.status.value == "inconclusive":
                inconclusive += 1

        self._run.total_checks = total
        self._run.passed = passed
        self._run.failed = failed
        self._run.skipped = skipped
        self._run.inconclusive = inconclusive

    @property
    def run(self) -> Optional[ReleaseRun]:
        """Get the current run."""
        return self._run


def run_release_qualification(dist_dir: str = "dist") -> ReleaseRun:
    """Convenience function to run release qualification."""
    runner = ReleaseRunner(dist_dir)
    return runner.run_all()
