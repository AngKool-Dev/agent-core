"""Git tools for Argus."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from argus.git_workflow import GitWorkflow, _git
from argus.workspace import validate_path, WorkspaceBoundaryError

from . import Tool, ToolResult


class GitStatusTool(Tool):
    name = "git_status"
    description = "Show the working tree status"

    def execute(self, project_path: str = ".", workspace: Optional[str] = None, **kwargs) -> ToolResult:
        if workspace:
            try:
                validate_path(project_path, workspace)
            except WorkspaceBoundaryError:
                return ToolResult(tool=self.name, success=False, error=f"Path '{project_path}' is outside workspace")
        return _git(["status", "--short", "--branch"], cwd=project_path)


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show changes between commits, commit and working tree, etc"

    def execute(self, project_path: str = ".", target: Optional[str] = None, workspace: Optional[str] = None, **kwargs) -> ToolResult:
        if workspace:
            try:
                validate_path(project_path, workspace)
            except WorkspaceBoundaryError:
                return ToolResult(tool=self.name, success=False, error=f"Path '{project_path}' is outside workspace")
        args = ["diff"]
        if target:
            args.append(target)
        return _git(args, cwd=project_path)


class GitLogTool(Tool):
    name = "git_log"
    description = "Show commit logs"

    def execute(self, project_path: str = ".", limit: int = 20, workspace: Optional[str] = None, **kwargs) -> ToolResult:
        if workspace:
            try:
                validate_path(project_path, workspace)
            except WorkspaceBoundaryError:
                return ToolResult(tool=self.name, success=False, error=f"Path '{project_path}' is outside workspace")
        fmt = "%H|%an|%ad|%s"
        args = ["log", f"--pretty=format:{fmt}", f"-n", str(limit)]
        return _git(args, cwd=project_path)


class GitAddTool(Tool):
    name = "git_add"
    description = "Stage files for commit"

    def execute(self, project_path: str = ".", paths: Optional[Union[str, List[str]]] = None, workspace: Optional[str] = None, **kwargs) -> ToolResult:
        if workspace:
            try:
                validate_path(project_path, workspace)
            except WorkspaceBoundaryError:
                return ToolResult(tool=self.name, success=False, error=f"Path '{project_path}' is outside workspace")
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

    def execute(self, project_path: str = ".", message: str = "", workspace: Optional[str] = None, **kwargs) -> ToolResult:
        if workspace:
            try:
                validate_path(project_path, workspace)
            except WorkspaceBoundaryError:
                return ToolResult(tool=self.name, success=False, error=f"Path '{project_path}' is outside workspace")
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


class GitWorkflowTool(Tool):
    name = "git_workflow"
    description = "Execute a Git workflow stage: inspect, review, test, approve, or commit"

    def __init__(self):
        self._workflows: Dict[str, GitWorkflow] = {}

    def _get_workflow(self, project_path: str) -> GitWorkflow:
        key = str(Path(project_path).resolve())
        if key not in self._workflows:
            self._workflows[key] = GitWorkflow(project_path)
        return self._workflows[key]

    def execute(
        self,
        stage: str = "inspect",
        project_path: str = ".",
        task_request: str = "",
        test_command: Optional[str] = None,
        recent_tools: Optional[List[str]] = None,
        recent_arguments: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            workflow = self._get_workflow(project_path)
            recent_tools = recent_tools or []
            recent_arguments = recent_arguments or []

            if stage == "inspect":
                state = workflow.inspect()
                if not state.get("is_git_repo"):
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=state.get("error", "Not a git repository"),
                        metadata={"stage": "inspect", "repo_state": state},
                    )
                return ToolResult(
                    tool=self.name,
                    success=True,
                    output=_format_inspect(state),
                    metadata={"stage": "inspect", "repo_state": state},
                )

            if stage == "review":
                diff_info = workflow.diff()
                if not diff_info.get("success"):
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=diff_info.get("error", "Diff failed"),
                        metadata={"stage": "review"},
                    )

                state = workflow.inspect()
                all_changes = state.get("all_changes", [])
                relevant, unrelated = workflow.identify_relevant_files(
                    all_changes, task_request, recent_tools, recent_arguments
                )

                return ToolResult(
                    tool=self.name,
                    success=True,
                    output=_format_review(diff_info, relevant, unrelated),
                    metadata={
                        "stage": "review",
                        "diff": diff_info,
                        "relevant": relevant,
                        "unrelated": unrelated,
                    },
                )

            if stage == "test":
                test_result = workflow.run_tests(test_command)
                return ToolResult(
                    tool=self.name,
                    success=test_result.get("success", False),
                    output=_format_test(test_result),
                    metadata={"stage": "test", "test_result": test_result},
                )

            if stage == "approve":
                state = workflow.inspect()
                diff_info = workflow.diff()
                all_changes = state.get("all_changes", [])
                relevant, unrelated = workflow.identify_relevant_files(
                    all_changes, task_request, recent_tools, recent_arguments
                )

                test_result = workflow.run_tests(test_command)
                summary = workflow.prepare_commit_summary(
                    task_request, test_result, diff_info, relevant, unrelated
                )

                return ToolResult(
                    tool=self.name,
                    success=True,
                    output=summary,
                    metadata={
                        "stage": "approve",
                        "needs_approval": True,
                        "approval_message": summary,
                        "relevant": relevant,
                        "unrelated": unrelated,
                    },
                )

            if stage == "commit":
                if not workflow.is_approved():
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error="Commit not approved. Call stage='approve' first and get user approval.",
                        metadata={"stage": "commit", "needs_approval": True},
                    )

                state = workflow.inspect()
                all_changes = state.get("all_changes", [])
                relevant, unrelated = workflow.identify_relevant_files(
                    all_changes, task_request, recent_tools, recent_arguments
                )

                if not relevant:
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error="No relevant files identified for commit",
                        metadata={"stage": "commit"},
                    )

                from argus.tools.git import GitAddTool, GitCommitTool

                add_result = GitAddTool().execute(project_path=project_path, paths=relevant)
                if not add_result.success:
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=f"git add failed: {add_result.error}",
                        metadata={"stage": "commit", "add_error": add_result.error},
                    )

                commit_message = workflow.get_commit_message() or task_request[:100]
                commit_result = GitCommitTool().execute(
                    project_path=project_path, message=commit_message
                )
                if not commit_result.success:
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=f"git commit failed: {commit_result.error}",
                        metadata={"stage": "commit", "commit_error": commit_result.error},
                    )

                return ToolResult(
                    tool=self.name,
                    success=True,
                    output=f"Committed: {commit_message}\n{commit_result.output}",
                    metadata={
                        "stage": "commit",
                        "committed_files": relevant,
                        "commit_message": commit_message,
                    },
                )

            return ToolResult(
                tool=self.name,
                success=False,
                error=f"Unknown workflow stage: {stage}",
                metadata={"stage": stage},
            )
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e), metadata={"stage": stage})


def _format_inspect(state: Dict[str, Any]) -> str:
    lines = [
        f"Branch: {state.get('branch', 'unknown')}",
        f"Staged: {len(state.get('staged', []))} file(s)",
        f"Modified: {len(state.get('changes', []))} file(s)",
        f"Untracked: {len(state.get('untracked', []))} file(s)",
    ]
    if state.get("staged"):
        lines.append("")
        lines.append("Staged files:")
        for f in state["staged"]:
            lines.append(f"  {f}")
    if state.get("changes"):
        lines.append("")
        lines.append("Modified files:")
        for f in state["changes"]:
            lines.append(f"  {f}")
    if state.get("untracked"):
        lines.append("")
        lines.append("Untracked files:")
        for f in state["untracked"]:
            lines.append(f"  {f}")
    return "\n".join(lines)


def _format_review(diff_info: Dict[str, Any], relevant: List[str], unrelated: List[str]) -> str:
    lines = [
        f"Diff: {diff_info.get('summary', 'No changes')}",
        f"Files changed: {', '.join(diff_info.get('files', [])[:10])}",
    ]
    if relevant:
        lines.append("")
        lines.append("Relevant files:")
        for f in relevant:
            lines.append(f"  {f}")
    if unrelated:
        lines.append("")
        lines.append("Unrelated files (not staged):")
        for f in unrelated:
            lines.append(f"  {f}")
    return "\n".join(lines)


def _format_test(test_result: Dict[str, Any]) -> str:
    if test_result.get("skipped"):
        return f"Tests: skipped ({test_result.get('reason', 'unknown')})"

    status = "PASSED" if test_result.get("passed") else "FAILED"
    lines = [f"Tests: {status}"]
    if test_result.get("command"):
        lines.append(f"Command: {test_result['command']}")
    if test_result.get("output"):
        lines.append(f"Output: {test_result['output'][:300]}")
    if test_result.get("error"):
        lines.append(f"Error: {test_result['error'][:300]}")
    return "\n".join(lines)
