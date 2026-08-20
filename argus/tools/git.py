"""Git tools for Argus."""

import subprocess
from pathlib import Path
from typing import List, Optional, Union

from . import Tool, ToolResult


def _git(args: List[str], cwd: str, timeout: int = 30) -> ToolResult:
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


class GitStatusTool(Tool):
    name = "git_status"
    description = "Show the working tree status"

    def execute(self, project_path: str = ".", **kwargs) -> ToolResult:
        return _git(["status", "--short", "--branch"], cwd=project_path)


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show changes between commits, commit and working tree, etc"

    def execute(self, project_path: str = ".", target: Optional[str] = None, **kwargs) -> ToolResult:
        args = ["diff"]
        if target:
            args.append(target)
        return _git(args, cwd=project_path)


class GitLogTool(Tool):
    name = "git_log"
    description = "Show commit logs"

    def execute(self, project_path: str = ".", limit: int = 20, **kwargs) -> ToolResult:
        fmt = "%H|%an|%ad|%s"
        args = ["log", f"--pretty=format:{fmt}", f"-n", str(limit)]
        return _git(args, cwd=project_path)


class GitAddTool(Tool):
    name = "git_add"
    description = "Stage files for commit"

    def execute(self, project_path: str = ".", paths: Optional[Union[str, List[str]]] = None, **kwargs) -> ToolResult:
        if not paths:
            return ToolResult(tool=self.name, success=False, error="No paths provided to git_add")

        safe_paths = _normalize_paths(paths)
        if not safe_paths:
            return ToolResult(tool=self.name, success=False, error="No valid paths provided to git_add")

        args = ["add"] + safe_paths
        return _git(args, cwd=project_path)


class GitCommitTool(Tool):
    name = "git_commit"
    description = "Record changes to the repository"

    def execute(self, project_path: str = ".", message: str = "", **kwargs) -> ToolResult:
        if not message or not message.strip():
            return ToolResult(tool=self.name, success=False, error="Commit message is required")

        args = ["commit", "-m", message.strip()]
        return _git(args, cwd=project_path)


def _normalize_paths(paths: Union[str, List[str]]) -> List[str]:
    if isinstance(paths, str):
        return [paths]

    normalized = []
    for p in paths:
        p = p.strip().strip('"').strip("'")
        if p:
            normalized.append(p)
    return normalized
