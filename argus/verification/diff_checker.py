"""Diff checker for verification."""

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from argus.verification.result import CriterionResult, VerificationStatus


@dataclass
class DiffFileChange:
    """A single file change in a diff."""
    path: str
    change_type: str  # added, modified, deleted, renamed
    additions: int = 0
    deletions: int = 0


@dataclass
class DiffResult:
    """Result of a diff check."""
    files: List[DiffFileChange] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    total_files: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": [
                {
                    "path": f.path,
                    "change_type": f.change_type,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
                for f in self.files
            ],
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "total_files": self.total_files,
        }


class DiffChecker:
    """Checks git diffs for verification."""

    def get_diff(
        self,
        project_path: str = ".",
        staged: bool = False,
        base_ref: str = "HEAD",
    ) -> DiffResult:
        """Get the current diff."""
        try:
            cmd = ["git", "diff", "--numstat"]
            if staged:
                cmd.append("--staged")
            else:
                cmd.append(base_ref)

            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return self._parse_numstat(result.stdout)
        except Exception:
            return DiffResult()

    def get_unstaged_diff(self, project_path: str = ".") -> DiffResult:
        """Get unstaged changes."""
        return self.get_diff(project_path=project_path, staged=False, base_ref="")

    def get_staged_diff(self, project_path: str = ".") -> DiffResult:
        """Get staged changes."""
        return self.get_diff(project_path=project_path, staged=True)

    def _parse_numstat(self, output: str) -> DiffResult:
        """Parse git diff --numstat output."""
        result = DiffResult()

        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                additions_str, deletions_str, path = parts[0], parts[1], parts[2]
                try:
                    additions = int(additions_str) if additions_str != "-" else 0
                    deletions = int(deletions_str) if deletions_str != "-" else 0
                except ValueError:
                    additions = 0
                    deletions = 0

                change = DiffFileChange(
                    path=path,
                    change_type="modified",
                    additions=additions,
                    deletions=deletions,
                )
                result.files.append(change)
                result.total_additions += additions
                result.total_deletions += deletions

        result.total_files = len(result.files)
        return result

    def check_max_files(self, max_files: int, project_path: str = ".") -> CriterionResult:
        """Check that no more than max_files have been changed."""
        start = time.time()
        diff = self.get_diff(project_path=project_path)
        duration = time.time() - start

        if diff.total_files <= max_files:
            return CriterionResult(
                name="max_files_changed",
                status=VerificationStatus.PASSED,
                message=f"{diff.total_files} files changed (max {max_files})",
                details=diff.to_dict(),
                duration=duration,
            )
        else:
            return CriterionResult(
                name="max_files_changed",
                status=VerificationStatus.FAILED,
                message=f"{diff.total_files} files changed (max {max_files})",
                details=diff.to_dict(),
                duration=duration,
            )

    def check_max_lines(self, max_lines: int, project_path: str = ".") -> CriterionResult:
        """Check that total changes don't exceed max_lines."""
        start = time.time()
        diff = self.get_diff(project_path=project_path)
        duration = time.time() - start
        total_lines = diff.total_additions + diff.total_deletions

        if total_lines <= max_lines:
            return CriterionResult(
                name="max_lines_changed",
                status=VerificationStatus.PASSED,
                message=f"{total_lines} lines changed (max {max_lines})",
                details=diff.to_dict(),
                duration=duration,
            )
        else:
            return CriterionResult(
                name="max_lines_changed",
                status=VerificationStatus.FAILED,
                message=f"{total_lines} lines changed (max {max_lines})",
                details=diff.to_dict(),
                duration=duration,
            )

    def check_no_files_matching(
        self,
        patterns: List[str],
        project_path: str = ".",
    ) -> CriterionResult:
        """Check that no changed files match the given patterns."""
        import re
        start = time.time()
        diff = self.get_diff(project_path=project_path)
        duration = time.time() - start

        violations = []
        for change in diff.files:
            for pattern in patterns:
                if re.search(pattern, change.path):
                    violations.append({"file": change.path, "pattern": pattern})

        if not violations:
            return CriterionResult(
                name="no_files_matching",
                status=VerificationStatus.PASSED,
                message="No files match forbidden patterns",
                duration=duration,
            )
        else:
            return CriterionResult(
                name="no_files_matching",
                status=VerificationStatus.FAILED,
                message=f"{len(violations)} files match forbidden patterns",
                details={"violations": violations},
                duration=duration,
            )

    def check_only_files_matching(
        self,
        patterns: List[str],
        project_path: str = ".",
    ) -> CriterionResult:
        """Check that only files matching the given patterns were changed."""
        import re
        start = time.time()
        diff = self.get_diff(project_path=project_path)
        duration = time.time() - start

        non_matching = []
        for change in diff.files:
            matches_any = any(re.search(pattern, change.path) for pattern in patterns)
            if not matches_any:
                non_matching.append(change.path)

        if not non_matching:
            return CriterionResult(
                name="only_files_matching",
                status=VerificationStatus.PASSED,
                message="All changed files match allowed patterns",
                duration=duration,
            )
        else:
            return CriterionResult(
                name="only_files_matching",
                status=VerificationStatus.FAILED,
                message=f"{len(non_matching)} files don't match allowed patterns",
                details={"non_matching": non_matching},
                duration=duration,
            )

    def get_changed_files(self, project_path: str = ".") -> List[str]:
        """Get list of changed file paths."""
        diff = self.get_diff(project_path=project_path)
        return [f.path for f in diff.files]