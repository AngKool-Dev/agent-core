"""Search tools for Argus."""

import re
from pathlib import Path
from typing import List, Optional

from argus.workspace import validate_path, WorkspaceBoundaryError

from . import Tool, ToolResult


class GrepTool(Tool):
    name = "grep"
    description = "Search file contents using regex"

    def execute(
        self,
        pattern: str,
        path: str = ".",
        include: Optional[str] = None,
        ignore_case: bool = False,
        limit: int = 100,
        workspace: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            workspace_path = Path(workspace) if workspace else None
            base = Path(path)
            if workspace_path:
                try:
                    base = validate_path(path, workspace_path)
                except WorkspaceBoundaryError:
                    return ToolResult(tool=self.name, success=False, error=f"Path '{path}' is outside workspace")

            if not base.exists():
                return ToolResult(tool=self.name, success=False, error=f"Path not found: {path}")

            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)
            matches = []

            files = self._iter_files(base, include)
            for file_path in files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            matches.append(f"{file_path}:{i}: {line}")
                            if len(matches) >= limit:
                                break
                except Exception:
                    continue
                if len(matches) >= limit:
                    break

            return ToolResult(
                tool=self.name,
                success=True,
                output="\n".join(matches) if matches else "No matches found",
                metadata={"matches": len(matches), "pattern": pattern},
            )
        except re.error as e:
            return ToolResult(tool=self.name, success=False, error=f"Invalid regex: {e}")
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))

    def _iter_files(self, base: Path, include: Optional[str]) -> List[Path]:
        if base.is_file():
            return [base]

        files = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                if include:
                    for pat in include.split(","):
                        if path.match(pat.strip()):
                            files.append(path)
                            break
                else:
                    files.append(path)
        return files


class GlobTool(Tool):
    name = "glob"
    description = "Find files matching a glob pattern"

    def execute(self, pattern: str, path: str = ".", workspace: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            workspace_path = Path(workspace) if workspace else None
            base = Path(path)
            if workspace_path:
                try:
                    base = validate_path(path, workspace_path)
                except WorkspaceBoundaryError:
                    return ToolResult(tool=self.name, success=False, error=f"Path '{path}' is outside workspace")

            if not base.exists():
                return ToolResult(tool=self.name, success=False, error=f"Path not found: {path}")

            matches = [str(p) for p in base.glob(pattern)]
            if not matches:
                matches = [str(p) for p in base.rglob(pattern)]

            return ToolResult(
                tool=self.name,
                success=True,
                output="\n".join(matches) if matches else "No matches found",
                metadata={"matches": len(matches), "pattern": pattern},
            )
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))
