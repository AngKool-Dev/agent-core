from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypedDict


class RuntimeCapabilities(TypedDict, total=False):
    """
    Standardized capability contract for runtime adapters.

    All fields are optional. Runtimes should advertise only the capabilities
    they actually support.
    """

    text_generation: bool
    tool_calls: bool
    external_tool_execution: bool
    streaming: bool
    cancellation: bool


@dataclass
class ToolCall:
    """A tool invocation requested by a runtime (model layer)."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    thought: str = ""
    id: str = field(default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "thought": self.thought,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        return cls(
            tool=data.get("tool", ""),
            arguments=data.get("arguments", {}),
            thought=data.get("thought", ""),
            id=data.get("id", ""),
        )


class FinishReason(StrEnum):
    """Why a runtime response ended."""

    STOP = "stop"  # Model produced final text, no more work needed
    TOOL_CALLS = "tool_calls"  # Model requested tool calls
    TIMEOUT = "timeout"  # Runtime timed out
    ERROR = "error"  # Runtime error occurred
    CANCELLED = "cancelled"  # Request was cancelled by caller


@dataclass
class RuntimeResponse:
    """
    Structured response from any RuntimeAdapter.

    The Agent processes this without knowing which runtime produced it.
    """

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_complete(self) -> bool:
        return self.finish_reason in (FinishReason.STOP, FinishReason.ERROR, FinishReason.TIMEOUT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "finish_reason": self.finish_reason.value
            if isinstance(self.finish_reason, FinishReason)
            else self.finish_reason,
            "metadata": self.metadata,
        }


class ToolResult:
    """
    Result of a tool execution.

    Standardized structure:
    - success: whether the tool ran without error
    - output: stdout / textual output (alias: stdout)
    - error: stderr / error message (alias: stderr)
    - metadata: additional structured data

    Accepts both ``output``/``stdout`` and ``error``/``stderr`` as keyword
    arguments for backward compatibility.
    """

    def __init__(
        self,
        success: bool,
        tool: str = "",
        output: str = "",
        error: str = "",
        exit_code: int = 0,
        duration: float = 0.0,
        metadata: dict[str, Any] | None = None,
        # backward-compat aliases
        stdout: str | None = None,
        stderr: str | None = None,
    ):
        self.success = success
        self.tool = tool
        self.output = stdout if stdout is not None else output
        self.error = stderr if stderr is not None else error
        self.exit_code = exit_code
        self.duration = duration
        self.metadata = metadata if metadata is not None else {}

    # --- backward-compatible property aliases ---
    @property
    def stdout(self) -> str:
        return self.output

    @stdout.setter
    def stdout(self, value: str) -> None:
        self.output = value

    @property
    def stderr(self) -> str:
        return self.error

    @stderr.setter
    def stderr(self, value: str) -> None:
        self.error = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tool": self.tool,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"ToolResult(success={self.success}, tool={self.tool!r}, "
            f"output={self.output[:80]!r}, error={self.error[:80]!r}, "
            f"exit_code={self.exit_code}, duration={self.duration})"
        )


class RuntimeAdapter(ABC):
    """
    Abstract interface for runtime adapters.

    A runtime adapter:
    - Invokes a model (e.g. Hermes CLI, Kilo, OpenCode)
    - Produces a structured RuntimeResponse
    - Exposes its capabilities
    - Handles cancellation and errors

    The runtime must NOT execute tools directly. Tool execution is
    the responsibility of ToolManager, orchestrated by the Agent.
    """

    @abstractmethod
    def respond(self, context: dict[str, Any]) -> RuntimeResponse:
        """Send a context/prompt to the model and return a structured response."""
        pass

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Return a dict describing what this runtime supports."""
        pass

    def cancel(self) -> None:
        """Request cancellation of an in-flight request. Default: no-op."""
        pass

    @property
    def default_model(self) -> str | None:
        """Return the default model name, if any."""
        return None


class HermesAPI:
    @staticmethod
    def build_prompt(context: dict[str, Any]) -> str:
        parts = []

        if "task" in context:
            task = context["task"]
            parts.append(f"Task: {task.get('user_request', '')}")
            parts.append(f"Project: {task.get('project', 'unknown')}")
            parts.append(f"State: {task.get('current_state', 'CREATED')}")

        if context.get("project_context"):
            parts.append("Project Context:")
            for key, value in list(context["project_context"].items())[:10]:
                if isinstance(value, (str, int, bool)):
                    parts.append(f"  {key}: {value}")
                elif isinstance(value, list):
                    parts.append(f"  {key}: {len(value)} items")

        if context.get("memory"):
            parts.append("Relevant Memory:")
            for item in context["memory"][:3]:
                content = item.get("content", "")[:200]
                parts.append(f"  {content}...")

        if context.get("skills"):
            parts.append(f"Selected Skills: {', '.join(context['skills'])}")

        if "instructions" in context:
            parts.append("Instructions:")
            for instr in context["instructions"]:
                parts.append(f"  {instr}")

        return "\n\n".join(parts) + "\n\n---\n\nUSER: " + context.get("user_request", "")
