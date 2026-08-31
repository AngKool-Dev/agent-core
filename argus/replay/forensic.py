"""ARGUS Replay forensic report - comprehensive run analysis."""

import json
import logging
from typing import Any, Dict, List, Optional

from argus.replay.models import (
    ReplayRun,
    RunStatus,
)
from argus.replay.timeline import ReplayTimeline
from argus.replay.consistency import ReplayConsistencyChecker
from argus.replay.diff import ReplayDiff
from argus.replay.tree import build_execution_tree, format_execution_tree
from argus.replay.reducer import StateReducer

logger = logging.getLogger(__name__)


class ForensicReport:
    """Comprehensive forensic report for a replay run."""

    def __init__(self, run: ReplayRun):
        self._run = run
        self._timeline = ReplayTimeline(run)
        self._consistency_checker = ReplayConsistencyChecker(run)
        self._diff = ReplayDiff()
        self._reducer = StateReducer()

    def generate(self) -> Dict[str, Any]:
        """Generate the complete forensic report.

        Returns:
            Dictionary with all report sections
        """
        consistency_issues = self._consistency_checker.check()
        execution_tree = build_execution_tree(self._run)
        final_state = self._reducer.reduce(self._run)

        report = {
            "overview": self._build_overview(),
            "execution_summary": self._build_execution_summary(),
            "security": self._build_security_section(),
            "recovery": self._build_recovery_section(),
            "verification": self._build_verification_section(),
            "review": self._build_review_section(),
            "state": self._build_state_section(final_state),
            "consistency": self._build_consistency_section(consistency_issues),
        }

        return report

    def to_json(self) -> str:
        """Generate JSON output for the report."""
        report = self.generate()
        return json.dumps(report, indent=2, default=str)

    def to_text(self) -> str:
        """Generate human-readable text report."""
        report = self.generate()
        lines = []

        # Overview
        overview = report["overview"]
        lines.append("ARGUS FORENSIC REPORT")
        lines.append("=" * 60)
        lines.append(f"Run ID: {overview['run_id']}")
        lines.append(f"Status: {overview['status']}")
        lines.append(f"Task: {overview.get('task', 'N/A')}")
        lines.append(f"Duration: {overview.get('duration', 'N/A')}s")
        lines.append(f"Events: {overview.get('event_count', 0)}")
        lines.append("")

        # Execution Summary
        exec_sum = report["execution_summary"]
        lines.append("EXECUTION SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Models Used: {exec_sum.get('models_used', 0)}")
        lines.append(f"Capabilities Used: {exec_sum.get('capabilities_used', 0)}")
        lines.append(f"Tool Calls: {exec_sum.get('tool_calls', 0)}")
        lines.append(f"Iterations: {exec_sum.get('iterations', 0)}")
        lines.append("")

        # Security
        security = report["security"]
        lines.append("SECURITY")
        lines.append("-" * 40)
        lines.append(f"Allowed: {security.get('allowed', 0)}")
        lines.append(f"Denied: {security.get('denied', 0)}")
        lines.append(f"Approvals: {security.get('approvals', 0)}")
        lines.append(f"Injection Events: {security.get('injection_events', 0)}")
        lines.append("")

        # Recovery
        recovery = report["recovery"]
        lines.append("RECOVERY")
        lines.append("-" * 40)
        lines.append(f"Failures: {recovery.get('failures', 0)}")
        lines.append(f"Strategies: {recovery.get('strategies', [])}")
        lines.append(f"Retries: {recovery.get('retries', 0)}")
        lines.append(f"Budget Consumed: {recovery.get('budget_consumed', 'N/A')}")
        lines.append("")

        # Verification
        verification = report["verification"]
        lines.append("VERIFICATION")
        lines.append("-" * 40)
        lines.append(f"Status: {verification.get('status', 'N/A')}")
        lines.append(f"Criteria: {verification.get('criteria', 0)}")
        lines.append(f"Passed: {verification.get('passed', 0)}")
        lines.append(f"Failed: {verification.get('failed', 0)}")
        lines.append("")

        # Review
        review = report["review"]
        lines.append("REVIEW")
        lines.append("-" * 40)
        lines.append(f"Status: {review.get('status', 'N/A')}")
        lines.append(f"Findings: {review.get('findings', 0)}")
        lines.append(f"Criteria Passed: {review.get('criteria_passed', 0)}")
        lines.append(f"Criteria Failed: {review.get('criteria_failed', 0)}")
        lines.append("")

        # State
        state = report["state"]
        lines.append("STATE")
        lines.append("-" * 40)
        lines.append(f"Files Changed: {state.get('files_changed', 0)}")
        lines.append(f"Files Added: {state.get('files_added', 0)}")
        lines.append(f"Files Deleted: {state.get('files_deleted', 0)}")
        lines.append("")

        # Consistency
        consistency = report["consistency"]
        lines.append("CONSISTENCY")
        lines.append("-" * 40)
        lines.append(f"Status: {consistency.get('status', 'N/A')}")
        lines.append(f"Warnings: {consistency.get('warnings', 0)}")
        lines.append(f"Errors: {consistency.get('errors', 0)}")

        if consistency.get("issues"):
            lines.append("\nIssues:")
            for issue in consistency["issues"]:
                lines.append(f"  [{issue.get('severity', 'unknown')}] {issue.get('description', '')}")

        return "\n".join(lines)

    def _build_overview(self) -> Dict[str, Any]:
        """Build the run overview section."""
        return {
            "run_id": self._run.run_id,
            "session_id": self._run.session_id,
            "task": self._run.task,
            "status": self._run.status.value,
            "started_at": self._run.started_at,
            "ended_at": self._run.ended_at,
            "duration": self._run.duration,
            "event_count": len(self._run.events),
        }

    def _build_execution_summary(self) -> Dict[str, Any]:
        """Build the execution summary section."""
        models = set()
        capabilities = set()
        tool_calls = 0

        for event in self._run.events:
            if event.category == "model":
                models.add(event.source)
            if event.category == "capability":
                capabilities.add(event.capability)
                tool_calls += 1

        return {
            "models_used": len(models),
            "model_sources": list(models),
            "capabilities_used": len(capabilities),
            "capabilities": list(capabilities),
            "tool_calls": tool_calls,
            "iterations": len([e for e in self._run.events if e.event_type == "step.started"]),
        }

    def _build_security_section(self) -> Dict[str, Any]:
        """Build the security section."""
        allowed = 0
        denied = 0
        approvals = 0
        injection_events = 0

        for decision in self._run.security_decisions:
            if decision.decision == "allowed":
                allowed += 1
            elif decision.decision == "denied":
                denied += 1
            elif decision.decision in ("approved", "approval_requested"):
                approvals += 1

        for event in self._run.events:
            if event.event_type == "security.injection_detected":
                injection_events += 1

        return {
            "allowed": allowed,
            "denied": denied,
            "approvals": approvals,
            "injection_events": injection_events,
            "total_decisions": len(self._run.security_decisions),
        }

    def _build_recovery_section(self) -> Dict[str, Any]:
        """Build the recovery section."""
        failures = len(self._run.recovery_actions)
        strategies = list(set(a.strategy for a in self._run.recovery_actions))
        retries = sum(1 for a in self._run.recovery_actions if a.strategy == "retry")

        return {
            "failures": failures,
            "strategies": strategies,
            "retries": retries,
            "budget_consumed": f"{failures}/{self._run.metadata.get('max_recovery_attempts', 'N/A')}",
            "actions": len(self._run.recovery_actions),
        }

    def _build_verification_section(self) -> Dict[str, Any]:
        """Build the verification section."""
        passed = sum(1 for v in self._run.verification_results if v.passed)
        failed = sum(1 for v in self._run.verification_results if not v.passed)

        status = "not_run"
        if self._run.verification_results:
            status = "passed" if failed == 0 else "failed"

        return {
            "status": status,
            "criteria": len(self._run.verification_results),
            "passed": passed,
            "failed": failed,
        }

    def _build_review_section(self) -> Dict[str, Any]:
        """Build the review section."""
        if not self._run.review_results:
            return {
                "status": "not_run",
                "findings": 0,
                "criteria_passed": 0,
                "criteria_failed": 0,
            }

        latest = self._run.review_results[-1]
        return {
            "status": latest.status,
            "findings": latest.findings_count,
            "criteria_passed": latest.criteria_passed,
            "criteria_failed": latest.criteria_failed,
        }

    def _build_state_section(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """Build the state section."""
        diff = self._diff.diff_states(self._run.initial_state, self._run.final_state)

        return {
            "files_changed": len(diff.files_modified),
            "files_added": len(diff.files_added),
            "files_deleted": len(diff.files_deleted),
            "plan_changes": len(diff.plan_changes),
            "assumption_changes": len(diff.assumption_changes),
            "learned_facts": len(diff.learned_facts_added),
        }

    def _build_consistency_section(self, issues: List[Any]) -> Dict[str, Any]:
        """Build the consistency section."""
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")

        status = "valid"
        if errors > 0:
            status = "invalid"
        elif warnings > 0:
            status = "warnings"

        return {
            "status": status,
            "warnings": warnings,
            "errors": errors,
            "issues": [i.to_dict() for i in issues],
        }


def generate_forensic_report(run: ReplayRun) -> ForensicReport:
    """Convenience function to generate a forensic report."""
    return ForensicReport(run)
