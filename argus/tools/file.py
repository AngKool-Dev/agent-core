"""File tools for Argus."""

import os
from pathlib import Path
from typing import Optional

from argus.workspace import validate_path, WorkspaceBoundaryError

from . import Tool, ToolResult


def _resolve_path(path: str, workspace: Optional[Path] = None, enforce_boundary: bool = True) -> Optional[Path]:
    if not enforce_boundary or workspace is None:
        return Path(path)
    try:
        return validate_path(path, workspace)
    except WorkspaceBoundaryError:
        return None


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file"

    def execute(self, path: str, offset: int = 0, limit: int = 2000, workspace: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            workspace_path = Path(workspace) if workspace else None
            resolved = _resolve_path(path, workspace_path, enforce_boundary=True)
            if resolved is None:
                return ToolResult(tool=self.name, success=False, error=f"Path '{path}' is outside workspace")

            file_path = resolved
            if not file_path.exists():
                return ToolResult(tool=self.name, success=False, error=f"File not found: {path}")

            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            total = len(lines)
            slice_lines = lines[offset : offset + limit]

            output = "\n".join(
                f"{i + 1 + offset}: {line}" for i, line in enumerate(slice_lines)
            )

            return ToolResult(
                tool=self.name,
                success=True,
                output=output,
                metadata={"total_lines": total, "offset": offset, "limit": limit},
            )
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file"

    def execute(self, path: str, content: str, mode: str = "overwrite", workspace: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            workspace_path = Path(workspace) if workspace else None
            resolved = _resolve_path(path, workspace_path, enforce_boundary=True)
            if resolved is None:
                return ToolResult(tool=self.name, success=False, error=f"Path '{path}' is outside workspace")

            file_path = resolved
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if mode == "append":
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(content)
            else:
                file_path.write_text(content, encoding="utf-8")

            return ToolResult(
                tool=self.name,
                success=True,
                output=f"Wrote {len(content)} bytes to {path}",
                metadata={"bytes_written": len(content), "mode": mode},
            )
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))


class EditFileTool(Tool):
    name = "edit_file"
    description = "Edit a file by replacing old_string with new_string"

    def execute(self, path: str, old_string: str, new_string: str, workspace: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            workspace_path = Path(workspace) if workspace else None
            resolved = _resolve_path(path, workspace_path, enforce_boundary=True)
            if resolved is None:
                return ToolResult(tool=self.name, success=False, error=f"Path '{path}' is outside workspace")

            file_path = resolved
            if not file_path.exists():
                return ToolResult(tool=self.name, success=False, error=f"File not found: {path}")

            content = file_path.read_text(encoding="utf-8")
            if old_string not in content:
                return ToolResult(
                    tool=self.name,
                    success=False,
                    error="old_string not found in file",
                )

            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return ToolResult(
                tool=self.name,
                success=True,
                output=f"Edited {path}",
                metadata={"replacements": 1},
            )
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))


class ListDirTool(Tool):
    name = "list_dir"
    description = "List contents of a directory"

    def execute(self, path: str = ".", workspace: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            workspace_path = Path(workspace) if workspace else None
            resolved = _resolve_path(path, workspace_path, enforce_boundary=True)
            if resolved is None:
                return ToolResult(tool=self.name, success=False, error=f"Path '{path}' is outside workspace")

            dir_path = resolved
            if not dir_path.exists():
                return ToolResult(tool=self.name, success=False, error=f"Directory not found: {path}")

            entries = []
            for entry in sorted(dir_path.iterdir()):
                entries.append(f"{'[DIR] ' if entry.is_dir() else '[FILE]'} {entry.name}")

            return ToolResult(
                tool=self.name,
                success=True,
                output="\n".join(entries),
                metadata={"count": len(entries)},
            )
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))
