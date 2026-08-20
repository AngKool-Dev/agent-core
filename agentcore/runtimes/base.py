from abc import ABC, abstractmethod
from typing import Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    thought: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "thought": self.thought,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        return cls(
            tool=data.get("tool", ""),
            arguments=data.get("arguments", {}),
            thought=data.get("thought", ""),
        )


@dataclass
class ToolResult:
    success: bool
    tool: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tool": self.tool,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "error": self.error,
        }


class RuntimeAdapter(ABC):
    @abstractmethod
    def respond(self, context: dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def get_response_text(self) -> str:
        pass

    @abstractmethod
    def is_complete(self) -> bool:
        pass


class HermesAPI:
    @staticmethod
    def build_prompt(context: dict[str, Any]) -> str:
        parts = []

        if "task" in context:
            task = context["task"]
            parts.append(f"Task: {task.get('user_request', '')}")
            parts.append(f"Project: {task.get('project', 'unknown')}")
            parts.append(f"State: {task.get('current_state', 'CREATED')}")

        if "project_context" in context and context["project_context"]:
            parts.append("Project Context:")
            for key, value in list(context["project_context"].items())[:10]:
                if isinstance(value, (str, int, bool)):
                    parts.append(f"  {key}: {value}")
                elif isinstance(value, list):
                    parts.append(f"  {key}: {len(value)} items")

        if "memory" in context and context["memory"]:
            parts.append("Relevant Memory:")
            for item in context["memory"][:3]:
                content = item.get("content", "")[:200]
                parts.append(f"  {content}...")

        if "skills" in context and context["skills"]:
            parts.append(f"Selected Skills: {', '.join(context['skills'])}")

        if "instructions" in context:
            parts.append("Instructions:")
            for instr in context["instructions"]:
                parts.append(f"  {instr}")

        return "\n\n".join(parts) + "\n\n---\n\nUSER: " + context.get("user_request", "")