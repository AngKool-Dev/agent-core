import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path

from agentcore.runtimes.base import ToolCall, ToolResult


@dataclass
class FileReadResult:
    path: str
    content: str
    exists: bool
    error: str | None = None


@dataclass
class FileWriteResult:
    path: str
    bytes_written: int
    success: bool
    error: str | None = None


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

    def __init__(self, project_path: str | Path | None = None, tool_timeout: int | None = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self._last_diff: str | None = None
        self._custom_tools: dict[str, callable] = {}
        self._tool_timeout = tool_timeout
        self._active_process: subprocess.Popen | None = None
        self._process_lock = threading.Lock()
        self._register_default_tools()

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(self, name: str, handler: callable) -> None:
        """
        Register a custom tool handler.

        The handler receives the tool arguments dict and must return a ToolResult.

        Example:
            def my_tool(args: dict) -> ToolResult:
                ...
            manager.register_tool("my_tool", my_tool)
        """
        self._custom_tools[name] = handler

    def _register_default_tools(self) -> None:
        """Register the built-in tool handlers."""
        self._custom_tools.update(
            {
                "read_file": self._tool_read_file,
                "write_file": self._tool_write_file,
                "search_files": self._tool_search_files,
                "run_command": self._tool_run_command,
                "git_status": self._tool_git_status,
                "git_diff": self._tool_git_diff,
                "git_diff_check": self._tool_git_diff_check,
                "run_tests": self._tool_run_tests,
                "check_format": self._tool_check_format,
                "check_build": self._tool_check_build,
            }
        )

    # ------------------------------------------------------------------
    # Unified dispatch: Agent calls this for every ToolCall from the runtime
    # ------------------------------------------------------------------

    def execute(self, tool_call: ToolCall, cwd: Path | None = None) -> ToolResult:
        """
        Dispatch a ToolCall to the appropriate handler and return a ToolResult.

        This is the single entry point the Agent uses to execute any tool
        requested by a model/runtime response.
        """
        tool_name = tool_call.tool
        args = tool_call.arguments
        start = time.time()
        work_dir = cwd if cwd is not None else self.project_path

        handler = self._custom_tools.get(tool_name)
        if handler is None:
            return ToolResult(
                success=False,
                tool=tool_name,
                output="",
                error=f"Unknown tool: {tool_name}",
                exit_code=1,
                duration=time.time() - start,
            )

        try:
            if self._tool_timeout is not None and self._tool_timeout > 0:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(handler, args, work_dir, start)
                    try:
                        return future.result(timeout=self._tool_timeout)
                    except FutureTimeoutError:
                        self._cancel_in_flight()
                        duration = time.time() - start
                        return ToolResult(
                            success=False,
                            tool=tool_name,
                            output="",
                            error=f"Tool timed out after {self._tool_timeout}s",
                            exit_code=124,
                            duration=duration,
                        )
            else:
                return handler(args, work_dir, start)
        except Exception as e:
            return ToolResult(
                success=False,
                tool=tool_name,
                output="",
                error=str(e),
                exit_code=1,
                duration=time.time() - start,
            )

    def cancel_in_flight(self) -> bool:
        """Request cancellation of any in-flight subprocess tool execution.

        Returns True if a subprocess was terminated, False if none was active.
        """
        return self._cancel_in_flight()

    def _cancel_in_flight(self) -> bool:
        """Terminate the active subprocess if one is running."""
        with self._process_lock:
            process = self._active_process
            if process is None:
                return False
            self._active_process = None

        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                return True
        except Exception:
            pass
        return False

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
    # Tool handler wrappers (called by registered tool callables)
    # ------------------------------------------------------------------

    def _tool_read_file(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        result = self.read_file(args.get("path", ""))
        return ToolResult(
            success=result.exists,
            tool="read_file",
            output=result.content,
            error=result.error or ("File not found" if not result.exists else ""),
            exit_code=0 if result.exists else 1,
            duration=time.time() - start,
        )

    def _tool_write_file(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        result = self.write_file(args.get("path", ""), args.get("content", ""))
        return ToolResult(
            success=result.success,
            tool="write_file",
            output=f"Wrote {result.bytes_written} bytes to {result.path}",
            error=result.error or "",
            exit_code=0 if result.success else 1,
            duration=time.time() - start,
        )

    def _tool_search_files(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        results = self.search_files(
            args.get("query", ""),
            path=args.get("path"),
            include=args.get("include"),
        )
        output = "\n".join(f"{r.path}:{r.line}: {r.content}" for r in results)
        return ToolResult(
            success=True,
            tool="search_files",
            output=output,
            error="",
            exit_code=0,
            duration=time.time() - start,
            metadata={"result_count": len(results)},
        )

    def _tool_run_command(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        cmd = args.get("command", "")
        timeout = int(args.get("timeout", 30))
        return self.shell(cmd, cwd=work_dir, timeout=timeout)

    def _tool_git_status(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        output = self.git_status()
        return ToolResult(
            success=True,
            tool="git_status",
            output=output,
            duration=time.time() - start,
        )

    def _tool_git_diff(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        output = self.git_diff(staged=args.get("staged", False))
        return self._last_diff_to_result("git_diff", output, start)

    def _tool_git_diff_check(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        errors = self.git_diff_check()
        return ToolResult(
            success=len(errors) == 0,
            tool="git_diff_check",
            output="\n".join(errors) if errors else "No whitespace errors",
            error="\n".join(errors) if errors else "",
            duration=time.time() - start,
            metadata={"error_count": len(errors)},
        )

    def _tool_run_tests(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        return self.run_tests(
            test_pattern=args.get("test_pattern"),
            verbose=args.get("verbose", False),
        )

    def _tool_check_format(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        return self.check_format()

    def _tool_check_build(self, args: dict, work_dir: Path, start: float) -> ToolResult:
        return self.check_build()

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
            return FileWriteResult(
                path=str(full_path), bytes_written=0, success=False, error=str(e)
            )

    def search_files(
        self, query: str, path: str | None = None, include: str | None = None
    ) -> list[SearchResult]:
        search_path = self.project_path if path is None else Path(path)
        if not search_path.exists():
            search_path = self.project_path

        results = []
        pattern = re.compile(query, re.IGNORECASE) if isinstance(query, str) else query

        for file_path in search_path.rglob("*"):
            if file_path.is_file():
                if include and file_path.suffix.lstrip(".") not in include:
                    continue
                if ".git" in str(file_path) or "node_modules" in str(file_path):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        if pattern.search(line):
                            results.append(
                                SearchResult(
                                    path=str(file_path.relative_to(self.project_path)),
                                    line=i,
                                    content=line[:200],
                                )
                            )
                except Exception:
                    continue

                if len(results) >= 100:
                    return results

        return results[:100]

    # ------------------------------------------------------------------
    # Shell
    # ------------------------------------------------------------------

    def shell(self, command: str, cwd: str | Path | None = None, timeout: int = 30) -> ToolResult:
        """Execute a shell command string.

        Contract: ``command`` is a shell-interpreted command string.  The tool
        intentionally uses ``shell=True`` because legitimate agent commands
        routinely rely on shell features (globs, pipes, redirects, env-var
        expansion, and shell builtins).  Callers should treat ``command`` as
        untrusted model output and rely on the surrounding AgentCore security
        boundary rather than trying to sanitize individual command strings here.
        """
        start = time.time()
        work_dir = Path(cwd) if cwd else self.project_path

        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=work_dir,
            )
            with self._process_lock:
                self._active_process = process
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                returncode = process.returncode
            finally:
                with self._process_lock:
                    if self._active_process is process:
                        self._active_process = None
            return ToolResult(
                success=returncode == 0,
                tool="shell",
                output=stdout,
                error=stderr,
                exit_code=returncode,
                duration=time.time() - start,
            )
        except subprocess.TimeoutExpired:
            self._cancel_in_flight()
            return ToolResult(
                success=False,
                tool="shell",
                output="",
                error=f"Command timed out after {timeout}s",
                exit_code=124,
                duration=time.time() - start,
            )
        except Exception as e:
            self._cancel_in_flight()
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

    def git_diff_check(self) -> list[str]:
        result = self.shell("git diff --check")
        errors = []
        if result.output:
            errors.extend(result.output.strip().split("\n"))
        if result.error:
            errors.extend(result.error.strip().split("\n"))
        return [e for e in errors if e]

    def get_git_changed_files(self) -> list[str]:
        result = self.shell("git diff --name-only")
        return [f for f in result.output.strip().split("\n") if f]

    # ------------------------------------------------------------------
    # Test / build / format tools
    # ------------------------------------------------------------------

    def run_tests(self, test_pattern: str | None = None, verbose: bool = False) -> ToolResult:
        cmd = ""
        if (self.project_path / "Cargo.toml").exists():
            cmd = "cargo test"
        elif (self.project_path / "pyproject.toml").exists() or (
            self.project_path / "setup.py"
        ).exists():
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
            return ToolResult(
                success=True,
                tool="check_format",
                output="",
                error="No format checker found",
                exit_code=0,
                duration=0,
            )

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
            return ToolResult(
                success=True, tool="check_build", output="", error="", exit_code=0, duration=0
            )

        return self.shell(build_cmd)


def create_tool_manager(project_path: str | Path | None = None) -> ToolManager:
    return ToolManager(project_path)
