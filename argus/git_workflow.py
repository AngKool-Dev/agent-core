"""Argus Git workflow helpers."""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _git(args: List[str], cwd: str, timeout: int = 30) -> "ToolResult":
    try:
        completed = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ""
        if completed.stdout:
            output += completed.stdout
        if completed.stderr:
            output += f"\n[stderr]\n{completed.stderr}"

        return ToolResult(
            tool="git",
            success=completed.returncode == 0,
            output=output.strip(),
            error="" if completed.returncode == 0 else f"Exit code: {completed.returncode}",
            metadata={"returncode": completed.returncode, "args": args},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(tool="git", success=False, error=f"Git command timed out after {timeout}s")
    except FileNotFoundError:
        return ToolResult(tool="git", success=False, error="Git is not installed or not in PATH")
    except Exception as e:
        return ToolResult(tool="git", success=False, error=str(e))


from argus.tools import ToolResult  # noqa: E402


class GitWorkflow:
    def __init__(self, project_path: str):
        self.project_path = str(Path(project_path).resolve())
        self._cached_status: Optional[ToolResult] = None
        self._cached_diff: Optional[ToolResult] = None
        self._cached_log: Optional[ToolResult] = None
        self._approved: bool = False
        self._commit_message: str = ""
        self._relevant_paths: List[str] = []

    def inspect(self) -> Dict[str, Any]:
        status = _git(["status", "--short", "--branch"], cwd=self.project_path)
        self._cached_status = status
        if not status.success:
            return {
                "is_git_repo": False,
                "error": status.error,
                "branch": "",
                "changes": [],
                "staged": [],
                "untracked": [],
            }

        branch = ""
        changes = []
        staged = []
        untracked = []
        for line in status.output.splitlines():
            if line.startswith("##"):
                branch = line[3:].strip()
            elif line.startswith("M ") or line.startswith("A ") or line.startswith("D "):
                changes.append(line[3:])
            elif line.startswith("??"):
                untracked.append(line[3:])
            else:
                changes.append(line[3:] if len(line) > 3 else line.strip())

        return {
            "is_git_repo": True,
            "branch": branch,
            "changes": changes,
            "staged": staged,
            "untracked": untracked,
            "all_changes": staged + changes + untracked,
        }

    def diff(self, target: Optional[str] = None) -> Dict[str, Any]:
        if self._cached_diff is None:
            args = ["diff"]
            if target:
                args.append(target)
            self._cached_diff = _git(args, cwd=self.project_path)

        if not self._cached_diff.success:
            return {"success": False, "error": self._cached_diff.error, "files": [], "summary": ""}

        files = []
        additions = 0
        deletions = 0
        current_file = None
        for line in self._cached_diff.output.splitlines():
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    a_path = parts[2]
                    b_path = parts[3]
                    current_file = b_path[2:] if b_path.startswith("b/") else a_path[2:] if a_path.startswith("a/") else a_path
                    files.append(current_file)
            elif line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1

        summary = f"{len(files)} file(s) changed, {additions} insertions(+), {deletions} deletions(-)"
        return {
            "success": True,
            "files": files,
            "additions": additions,
            "deletions": deletions,
            "summary": summary,
            "output": self._cached_diff.output,
        }

    def log(self, limit: int = 5) -> Dict[str, Any]:
        if self._cached_log is None:
            fmt = "%H|%an|%ad|%s"
            args = ["log", f"--pretty=format:{fmt}", f"-n", str(limit)]
            self._cached_log = _git(args, cwd=self.project_path)

        if not self._cached_log.success:
            return {"success": False, "error": self._cached_log.error, "commits": []}

        commits = []
        for line in self._cached_log.output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3],
                })

        return {"success": True, "commits": commits}

    def run_tests(self, test_command: Optional[str] = None) -> Dict[str, Any]:
        if not test_command:
            return {"success": True, "skipped": True, "reason": "No test command configured"}

        result = _git(["run", "--no-commit", "--no-pager", test_command], cwd=self.project_path, timeout=120)
        if result.success:
            return {
                "success": True,
                "passed": True,
                "output": result.output,
                "command": test_command,
            }
        return {
            "success": False,
            "passed": False,
            "output": result.output,
            "error": result.error,
            "command": test_command,
        }

    def identify_relevant_files(
        self,
        changed_files: List[str],
        task_request: str,
        recent_tools: List[str],
        recent_arguments: List[Dict[str, Any]],
    ) -> Tuple[List[str], List[str]]:
        relevant: List[str] = []
        unrelated: List[str] = []

        task_keywords = set(task_request.lower().split())
        file_keywords = set()
        recent_paths = set()
        for arg in recent_arguments:
            path = arg.get("path", "")
            if path:
                file_keywords.update(Path(path).stem.lower().split("_"))
                file_keywords.update(Path(path).suffix.lower().split("."))
                try:
                    recent_paths.add(str(Path(path).resolve()))
                except Exception:
                    pass

        for f in changed_files:
            f_lower = f.lower()
            stem = Path(f).stem.lower()
            extension = Path(f).suffix.lower()

            is_relevant = False
            if any(kw in f_lower for kw in task_keywords if len(kw) > 3):
                is_relevant = True
            if any(kw in stem for kw in file_keywords if len(kw) > 3):
                is_relevant = True
            if extension in (".py", ".rs", ".js", ".ts", ".go", ".java", ".rb", ".php"):
                try:
                    f_resolved = str(Path(f).resolve())
                except Exception:
                    f_resolved = f
                if f_resolved in recent_paths:
                    is_relevant = True

            if is_relevant:
                relevant.append(f)
            else:
                unrelated.append(f)

        return relevant, unrelated

    def prepare_commit_summary(
        self,
        request: str,
        test_result: Dict[str, Any],
        diff_info: Dict[str, Any],
        relevant_files: List[str],
        unrelated_files: List[str],
    ) -> str:
        lines = [
            "Argus completed the requested change.",
            "",
            f"Repository: {self.project_path}",
            "",
            "Changes:",
        ]
        for f in relevant_files:
            lines.append(f"  M {f}")
        if unrelated_files:
            lines.append("")
            lines.append("Unrelated changes (not staged):")
            for f in unrelated_files:
                lines.append(f"  M {f}")

        lines.append("")
        lines.append(f"Tests: {'PASSED' if test_result.get('passed') else 'FAILED'}")
        if test_result.get("output"):
            lines.append(f"Test output: {test_result['output'][:200]}")

        lines.append("")
        lines.append(f"Diff: {diff_info.get('summary', 'No changes')}")
        lines.append("")
        lines.append("Proposed commit:")
        lines.append(f"  {request[:100]}")

        return "\n".join(lines)

    def set_approved(self, approved: bool, commit_message: str = "") -> None:
        self._approved = approved
        self._commit_message = commit_message

    def is_approved(self) -> bool:
        return self._approved

    def get_commit_message(self) -> str:
        return self._commit_message
