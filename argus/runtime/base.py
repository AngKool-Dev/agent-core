"""Argus runtime adapter base."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    tool: str
    arguments: Dict[str, Any]
    call_id: str = ""


@dataclass
class ToolResult:
    call_id: str
    success: bool
    output: str = ""
    error: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RuntimeAdapter(ABC):
    @abstractmethod
    def respond(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def execute_tool(self, tool_call: ToolCall, project_path: str) -> ToolResult:
        ...

    def get_pending_tool_call(self) -> Optional[ToolCall]:
        return None

    def clear_tool_call(self) -> None:
        pass

    def is_complete(self) -> bool:
        return False
