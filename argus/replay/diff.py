"""ARGUS Replay state diff - compares states at different points."""

import copy
from typing import Any, Dict, List, Optional, Set

from argus.replay.models import (
    ReplayRun,
    StateDiff,
)


class ReplayDiff:
    """Compare states at different points in a run."""

    def diff_states(
        self,
        state1: Dict[str, Any],
        state2: Dict[str, Any],
    ) -> StateDiff:
        """Compare two states and return differences.

        Args:
            state1: The earlier state
            state2: The later state

        Returns:
            StateDiff with all differences
        """
        diff = StateDiff()

        # Compare files
        files1 = set(state1.get("files", {}).keys())
        files2 = set(state2.get("files", {}).keys())

        diff.files_added = list(files2 - files1)
        diff.files_deleted = list(files1 - files2)

        # Modified files
        for file_path in files1 & files2:
            if state1["files"][file_path] != state2["files"][file_path]:
                diff.files_modified.append(file_path)

        # Compare plan
        plan1 = set(str(s) for s in state1.get("plan", []))
        plan2 = set(str(s) for s in state2.get("plan", []))
        if plan1 != plan2:
            diff.plan_changes = list(plan2 - plan1)

        # Compare assumptions
        assumptions1 = set(str(a) for a in state1.get("assumptions", {}).items())
        assumptions2 = set(str(a) for a in state2.get("assumptions", {}).items())
        if assumptions1 != assumptions2:
            diff.assumption_changes = list(assumptions2 - assumptions1)

        # Compare learned facts
        facts1 = set(state1.get("learned_facts", []))
        facts2 = set(state2.get("learned_facts", []))
        diff.learned_facts_added = list(facts2 - facts1)

        # Compare verification results
        ver1 = set(str(v) for v in state1.get("verification_results", []))
        ver2 = set(str(v) for v in state2.get("verification_results", []))
        if ver1 != ver2:
            diff.verification_changes = list(ver2 - ver1)

        # Compare recovery state
        rec1 = str(state1.get("recovery_state", {}))
        rec2 = str(state2.get("recovery_state", {}))
        if rec1 != rec2:
            diff.recovery_changes = [f"recovery_state changed"]

        return diff

    def diff_run_states(self, run: ReplayRun) -> StateDiff:
        """Diff initial and final state of a run.

        Args:
            run: The replay run

        Returns:
            StateDiff between initial and final state
        """
        return self.diff_states(run.initial_state, run.final_state)

    def diff_against_checkpoint(
        self,
        run: ReplayRun,
        checkpoint_state: Dict[str, Any],
    ) -> StateDiff:
        """Diff final state against a checkpoint state.

        Args:
            run: The replay run
            checkpoint_state: The checkpoint state to compare against

        Returns:
            StateDiff between checkpoint and final state
        """
        return self.diff_states(checkpoint_state, run.final_state)

    def format_diff(self, diff: StateDiff) -> str:
        """Format a StateDiff as a string."""
        lines = []

        if diff.files_added:
            lines.append("Files Added:")
            for f in diff.files_added:
                lines.append(f"  + {f}")

        if diff.files_modified:
            lines.append("Files Modified:")
            for f in diff.files_modified:
                lines.append(f"  ~ {f}")

        if diff.files_deleted:
            lines.append("Files Deleted:")
            for f in diff.files_deleted:
                lines.append(f"  - {f}")

        if diff.plan_changes:
            lines.append("Plan Changes:")
            for c in diff.plan_changes:
                lines.append(f"  ~ {c}")

        if diff.assumption_changes:
            lines.append("Assumption Changes:")
            for c in diff.assumption_changes:
                lines.append(f"  ~ {c}")

        if diff.learned_facts_added:
            lines.append("Learned Facts Added:")
            for f in diff.learned_facts_added:
                lines.append(f"  + {f}")

        if diff.verification_changes:
            lines.append("Verification Changes:")
            for c in diff.verification_changes:
                lines.append(f"  ~ {c}")

        if diff.recovery_changes:
            lines.append("Recovery Changes:")
            for c in diff.recovery_changes:
                lines.append(f"  ~ {c}")

        if not lines:
            lines.append("No changes detected.")

        return "\n".join(lines)
