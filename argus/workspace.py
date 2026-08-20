"""Argus workspace boundaries."""

import os
from pathlib import Path
from typing import Optional, Union


class WorkspaceBoundaryError(Exception):
    def __init__(self, path: str, workspace: str):
        self.path = path
        self.workspace = workspace
        super().__init__(f"Path '{path}' is outside workspace '{workspace}'")


def validate_path(path: Union[str, Path], workspace: Union[str, Path], allow_outside: bool = False) -> Path:
    resolved = Path(path).resolve()
    workspace_resolved = Path(workspace).resolve()

    if allow_outside:
        return resolved

    try:
        resolved.relative_to(workspace_resolved)
        return resolved
    except ValueError:
        raise WorkspaceBoundaryError(str(resolved), str(workspace_resolved))


def is_path_safe(path: Union[str, Path], workspace: Union[str, Path]) -> bool:
    try:
        validate_path(path, workspace)
        return True
    except WorkspaceBoundaryError:
        return False


def get_workspace_root(project_path: Union[str, Path]) -> Path:
    return Path(project_path).resolve()
