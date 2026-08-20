"""Argus tool system."""

import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from argus.permissions import PermissionConfig, PermissionDeniedError, check_permission


@dataclass
class ToolResult:
    tool: str
    success: bool
    output: str = ""
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


class Tool(ABC):
    name: str = "base"
    description: str = "Base tool"

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        ...

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {},
        }


class ToolRegistry:
    def __init__(
        self,
        permissions: Optional[PermissionConfig] = None,
        ask_callback: Optional[Callable[[str, str], bool]] = None,
    ):
        self._tools: Dict[str, Tool] = {}
        self._permissions = permissions or PermissionConfig()
        self._ask_callback = ask_callback

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(tool=name, success=False, error=f"Unknown tool: {name}")

        try:
            if not check_permission(name, self._permissions, self._ask_callback):
                raise PermissionDeniedError(name, "Permission not granted")
        except PermissionDeniedError as e:
            return ToolResult(tool=name, success=False, error=str(e))

        try:
            return tool.execute(**kwargs)
        except PermissionDeniedError as e:
            return ToolResult(tool=name, success=False, error=str(e))
        except Exception as e:
            return ToolResult(tool=name, success=False, error=str(e))

    def set_permissions(self, permissions: PermissionConfig) -> None:
        self._permissions = permissions

    def set_ask_callback(self, callback: Callable[[str, str], bool]) -> None:
        self._ask_callback = callback
