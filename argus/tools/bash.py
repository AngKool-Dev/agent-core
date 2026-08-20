"""Bash tool for Argus."""

import shlex
import subprocess
import sys
from typing import Optional

from . import Tool, ToolResult


class BashTool(Tool):
    name = "bash"
    description = "Execute a shell command"

    def execute(self, command: str, cwd: Optional[str] = None, timeout: int = 120, **kwargs) -> ToolResult:
        try:
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
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))
