"""Bash tool for Argus."""

import shlex
import subprocess
import sys
from typing import Optional

from . import Tool, ToolResult


DANGEROUS_PATTERNS = [
    "rm ",
    "del ",
    "rmdir ",
    "format ",
    "shutdown",
    "reboot",
    "git reset",
    "git clean",
    "drop database",
    "truncate ",
    "> /dev/",
    "mkfs",
    "dd ",
    ":(){ :|:& };",
]


class BashTool(Tool):
    name = "bash"
    description = "Execute a shell command"

    def __init__(self):
        self._process = None

    def execute(self, command: str, cwd: Optional[str] = None, timeout: int = 120, **kwargs) -> ToolResult:
        try:
            lower_command = command.lower()
            chained = any(sep in lower_command for sep in [" && ", " ; ", " || "])
            if chained:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error=f"Command chaining is not allowed: '{command}'",
                )

            for pattern in DANGEROUS_PATTERNS:
                if pattern in lower_command:
                    return ToolResult(
                        tool=self.name,
                        success=False,
                        error=f"Dangerous command blocked: pattern '{pattern}' detected in '{command}'",
                    )

            if sys.platform == "win32":
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                completed = subprocess.run(
                    shlex.split(command),
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
                tool=self.name,
                success=completed.returncode == 0,
                output=output.strip(),
                error="" if completed.returncode == 0 else f"Exit code: {completed.returncode}",
                metadata={"returncode": completed.returncode},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(tool=self.name, success=False, error=f"Command timed out after {timeout}s")
        except KeyboardInterrupt:
            return ToolResult(tool=self.name, success=False, error="Command was cancelled")
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))

    def cancel(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.kill()
            self._process.wait()
