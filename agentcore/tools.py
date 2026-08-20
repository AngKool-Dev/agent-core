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
    def __init__(self, project_path: Optional[str | Path] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self._last_diff: Optional[str] = None

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

        return results[:100]

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
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration=time.time() - start,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool="shell",
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=124,
                duration=time.time() - start,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                tool="shell",
                stdout="",
                stderr=str(e),
                exit_code=1,
                duration=time.time() - start,
            )

    def git_status(self) -> str:
        result = self.shell("git status --porcelain")
        return result.stdout

    def git_diff(self, staged: bool = False) -> str:
        cmd = "git diff --cached" if staged else "git diff"
        result = self.shell(cmd)
        self._last_diff = result.stdout if result.success else ""
        return self._last_diff

    def git_diff_check(self) -> List[str]:
        result = self.shell("git diff --check")
        errors = []
        if result.stdout:
            errors.extend(result.stdout.strip().split("\n"))
        if result.stderr:
            errors.extend(result.stderr.strip().split("\n"))
        return errors

    def get_git_changed_files(self) -> List[str]:
        result = self.shell("git diff --name-only")
        return [f for f in result.stdout.strip().split("\n") if f]

    def run_tests(self, test_pattern: Optional[str] = None, verbose: bool = False) -> ToolResult:
        pass_cmd = ""

        if (self.project_path / "Cargo.toml").exists():
            pass_cmd = "cargo test"
        elif (self.project_path / "pyproject.toml").exists() or (self.project_path / "setup.py").exists():
            pass_cmd = "pytest"
        elif (self.project_path / "package.json").exists():
            pass_cmd = "npm test"

        if not pass_cmd:
            return ToolResult(
                success=False,
                tool="tests",
                stdout="",
                stderr="No test runner found for this project",
                exit_code=1,
                duration=0,
            )

        if test_pattern:
            pass_cmd = f"{pass_cmd} {test_pattern}"

        return self.shell(pass_cmd, timeout=120)

    def check_format(self) -> ToolResult:
        check_cmd = ""

        if (self.project_path / "Cargo.toml").exists():
            check_cmd = "cargo fmt --check"
        elif (self.project_path / "pyproject.toml").exists():
            check_cmd = "ruff format --check"
        elif (self.project_path / "package.json").exists():
            check_cmd = "npx prettier --check '**/*.{js,ts,jsx,tsx,json,css,md}'"
        
        if not check_cmd:
            return ToolResult(success=False, tool="format", stdout="", stderr="No format checker found", exit_code=1, duration=0)

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
            return ToolResult(success=True, tool="build", stdout="No build step required", stderr="", exit_code=0, duration=0)

        return self.shell(build_cmd)


def create_tool_manager(project_path: Optional[str | Path] = None) -> ToolManager:
    return ToolManager(project_path)