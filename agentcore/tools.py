import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentcore.runtimes.base import ToolCall, ToolResult


@dataclass
class FileReadResult:
    path: str
    content: str
    exists: bool
    error: Optional[str] = None


@dataclass
class FileWriteResult:
    path: str
    bytes_written: int
    success: bool
    error: Optional[str] = None


@dataclass
class SearchResult:
    path: str
    line: int
    content: str


class ToolManager:
    """
    Central tool executor for AgentCore.

    Owns ALL filesystem, shell, git, search, build, format, and test operations.
    Runtime adapters delegate tool execution decisions here rather than
    implementing their own copies.
    """

    def __init__(self, project_path: Optional[str | Path] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self._last_diff: Optional[str] = None

    # ------------------------------------------------------------------
    # Unified dispatch: Agent calls this for every ToolCall from the runtime
    # ------------------------------------------------------------------

    def execute(self, tool_call: ToolCall, cwd: Optional[Path] = None) -> ToolResult:
        """
        Dispatch a ToolCall to the appropriate handler and return a ToolResult.

        This is the single entry point the Agent uses to execute any tool
        requested by a model/runtime response.
        """
        tool_name = tool_call.tool
        args = tool_call.arguments
        start = time.time()
        work_dir = cwd if cwd is not None else self.project_path

        try:
            if tool_name == "read_file":
                result = self.read_file(args.get("path", ""))
                return ToolResult(
                    success=result.exists,
                    tool=tool_name,
                    output=result.content,
                    error=result.error or ("File not found" if not result.exists else ""),
                    exit_code=0 if result.exists else 1,
                    duration=time.time() - start,
                )

            elif tool_name == "write_file":
                result = self.write_file(args.get("path", ""), args.get("content", ""))
                return ToolResult(
                    success=result.success,
                    tool=tool_name,
                    output=f"Wrote {result.bytes_written} bytes to {result.path}",
                    error=result.error or "",
                    exit_code=0 if result.success else 1,
                    duration=time.time() - start,
                )

            elif tool_name == "search_files":
                results = self.search_files(
                    args.get("query", ""),
                    path=args.get("path"),
                    include=args.get("include"),
                )
                output = "\n".join(f"{r.path}:{r.line}: {r.content}" for r in results)
                return ToolResult(
                    success=True,
                    tool=tool_name,
                    output=output,
                    error="",
                    exit_code=0,
                    duration=time.time() - start,
                    metadata={"result_count": len(results)},
                )

            elif tool_name == "run_command":
                cmd = args.get("command", "")
                timeout = int(args.get("timeout", 30))
                return self.shell(cmd, cwd=work_dir, timeout=timeout)

            elif tool_name == "git_status":
                output = self.git_status()
                return ToolResult(
                    success=True,
                    tool=tool_name,
                    output=output,
                    duration=time.time() - start,
                )

            elif tool_name == "git_diff":
                output = self.git_diff(staged=args.get("staged", False))
                return self._last_diff_to_result(tool_name, output, start)

            elif tool_name == "git_diff_check":
                errors = self.git_diff_check()
                return ToolResult(
                    success=len(errors) == 0,
                    tool=tool_name,
                    output="\n".join(errors) if errors else "No whitespace errors",
                    error="\n".join(errors) if errors else "",
                    duration=time.time() - start,
                    metadata={"error_count": len(errors)},
                )

            elif tool_name == "run_tests":
                return self.run_tests(
                    test_pattern=args.get("test_pattern"),
                    verbose=args.get("verbose", False),
                )

            elif tool_name == "check_format":
                return self.check_format()

            elif tool_name == "check_build":
                return self.check_build()

            else:
                return ToolResult(
                    success=False,
                    tool=tool_name,
                    output="",
                    error=f"Unknown tool: {tool_name}",
                    exit_code=1,
                    duration=time.time() - start,
                )

        except Exception as e:
            return ToolResult(
                success=False,
                tool=tool_name,
                output="",
                error=str(e),
                exit_code=1,
                duration=time.time() - start,
            )

    def _last_diff_to_result(self, tool_name: str, output: str, start: float) -> ToolResult:
        return ToolResult(
            success=True,
            tool=tool_name,
            output=output,
            error="",
            exit_code=0,
            duration=time.time() - start,
        )

    # ------------------------------------------------------------------
    # Filesystem tools
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> FileReadResult:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.project_path / path

        if not full_path.exists():
            return FileReadResult(path=path, content="", exists=False, error="File not found")

        try:
            content = full_path.read_text(encoding="utf-8")
            return FileReadResult(path=str(full_path), content=content, exists=True)
        except Exception as e:
            return FileReadResult(path=str(full_path), content="", exists=False, error=str(e))

    def write_file(self, path: str, content: str) -> FileWriteResult:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.project_path / path

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return FileWriteResult(
                path=str(full_path),
                bytes_written=len(content),
                success=True,
            )
        except Exception as e:
            return FileWriteResult(path=str(full_path), bytes_written=0, success=False, error=str(e))

    def search_files(self, query: str, path: Optional[str] = None, include: Optional[str] = None) -> List[SearchResult]:
        search_path = self.project_path if path is None else Path(path)
        if not search_path.exists():
            search_path = self.project_path

        results = []
        pattern = re.compile(query, re.IGNORECASE) if isinstance(query, str) else query

        for file_path in search_path.rglob("*"):
            if file_path.is_file():
                if include and not file_path.suffix.lstrip(".") in include:
                    continue
                if ".git" in str(file_path) or "node_modules" in str(file_path):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        if pattern.search(line):
                            results.append(SearchResult(
                                path=str(file_path.relative_to(self.project_path)),
                                line=i,
                                content=line[:200],
                            ))
                except Exception:
                    continue

                if len(results) >= 100:
                    return results

        return results[:100]

    # ------------------------------------------------------------------
    # Shell
    # ------------------------------------------------------------------

    def shell(self, command: str, cwd: Optional[str | Path] = None, timeout: int = 30) -> ToolResult:
        start = time.time()
        work_dir = Path(cwd) if cwd else self.project_path

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=timeout,
            )
            return ToolResult(
                success=result.returncode == 0,
                tool="shell",
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
                duration=time.time() - start,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool="shell",
                output="",
                error=f"Command timed out after {timeout}s",
                exit_code=124,
                duration=time.time() - start,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                tool="shell",
                output="",
                error=str(e),
                exit_code=1,
                duration=time.time() - start,
            )

    # ------------------------------------------------------------------
    # Git tools
    # ------------------------------------------------------------------

    def git_status(self) -> str:
        result = self.shell("git status --porcelain")
        return result.output

    def git_diff(self, staged: bool = False) -> str:
        cmd = "git diff --cached" if staged else "git diff"
        result = self.shell(cmd)
        self._last_diff = result.output if result.success else ""
        return self._last_diff

    def git_diff_check(self) -> List[str]:
        result = self.shell("git diff --check")
        errors = []
        if result.output:
            errors.extend(result.output.strip().split("\n"))
        if result.error:
            errors.extend(result.error.strip().split("\n"))
        return [e for e in errors if e]

    def get_git_changed_files(self) -> List[str]:
        result = self.shell("git diff --name-only")
        return [f for f in result.output.strip().split("\n") if f]

    # ------------------------------------------------------------------
    # Test / build / format tools
    # ------------------------------------------------------------------

    def run_tests(self, test_pattern: Optional[str] = None, verbose: bool = False) -> ToolResult:
        cmd = ""
        if (self.project_path / "Cargo.toml").exists():
            cmd = "cargo test"
        elif (self.project_path / "pyproject.toml").exists() or (self.project_path / "setup.py").exists():
            cmd = "pytest"
        elif (self.project_path / "package.json").exists():
            cmd = "npm test"

        if not cmd:
            return ToolResult(
                success=False,
                tool="run_tests",
                output="",
                error="No test runner found for this project",
                exit_code=1,
                duration=0,
            )

        if test_pattern:
            if "pytest" in cmd:
                cmd = f"{cmd} -k {test_pattern}"
            else:
                cmd = f"{cmd} {test_pattern}"

        if verbose:
            if "pytest" in cmd or "cargo" in cmd:
                cmd = cmd + " -v"

        return self.shell(cmd, timeout=120)

    def check_format(self) -> ToolResult:
        check_cmd = ""
        if (self.project_path / "Cargo.toml").exists():
            check_cmd = "cargo fmt --check"
        elif (self.project_path / "pyproject.toml").exists():
            check_cmd = "ruff format --check"
        elif (self.project_path / "package.json").exists():
            check_cmd = "npx prettier --check '**/*.{js,ts,jsx,tsx,json,css,md}'"

        if not check_cmd:
            return ToolResult(success=True, tool="check_format", output="", error="No format checker found", exit_code=0, duration=0)

        return self.shell(check_cmd)

    def check_build(self) -> ToolResult:
        build_cmd = ""
        if (self.project_path / "Cargo.toml").exists():
            build_cmd = "cargo check"
        elif (self.project_path / "pyproject.toml").exists():
            build_cmd = "python -m py_compile ."
        elif (self.project_path / "package.json").exists():
            build_cmd = "npm run build"

        if not build_cmd:
            return ToolResult(success=True, tool="check_build", output="", error="", exit_code=0, duration=0)

        return self.shell(build_cmd)


def create_tool_manager(project_path: Optional[str | Path] = None) -> ToolManager:
    return ToolManager(project_path)
