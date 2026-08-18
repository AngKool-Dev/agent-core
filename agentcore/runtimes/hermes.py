import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from .base import (
    RuntimeAdapter,
    RuntimeResponse,
    ToolCall,
    ToolResult,
    FinishReason,
    HermesAPI,
)


TOOL_CALL_PATTERN = re.compile(
    r"TOOL_CALL:\s*(\w+)\s*\{([^}]*)\}",
    re.IGNORECASE,
)

ARGUMENT_PATTERN = re.compile(r'"(\w+)"\s*:\s*"([^"]*)"')

# Marker the Hermes CLI uses to signal completion
COMPLETE_MARKER = "COMPLETE"


class HermesRuntime(RuntimeAdapter):
    """
    Runtime adapter that drives the Hermes CLI (`hermes -z`).

    Responsibilities:
    - Build a prompt from the AgentCore context
    - Invoke the Hermes CLI as a subprocess
    - Parse the text response to extract normal content and tool calls
    - Return a structured RuntimeResponse

    This runtime does NOT execute tools, run shell commands, read files,
    or perform any build/test/format operations. Those are handled by
    ToolManager, orchestrated by the Agent.
    """

    def __init__(self, model: Optional[str] = None, provider: Optional[str] = None, timeout: int = 300):
        self.model = model
        self.provider = provider
        self.timeout = timeout
        self._last_response: Optional[RuntimeResponse] = None

    def respond(self, context: dict[str, Any]) -> RuntimeResponse:
        """Send a context to the Hermes CLI and return a structured response."""
        full_prompt = HermesAPI.build_prompt(context)

        hermes_args = ["hermes", "-z"]
        if self.model:
            hermes_args.extend(["-m", self.model])
        if self.provider:
            hermes_args.extend(["--provider", self.provider])

        try:
            result = subprocess.run(
                hermes_args + [full_prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            response_text = result.stdout.strip() if result.stdout else ""
            stderr_text = result.stderr.strip() if result.stderr else ""

            parsed = self._parse_response(response_text, stderr_text, result.returncode)
            self._last_response = parsed
            return parsed

        except subprocess.TimeoutExpired:
            response = RuntimeResponse(
                content="",
                tool_calls=[],
                finish_reason=FinishReason.TIMEOUT,
                metadata={"stderr": f"Hermes call timed out after {self.timeout}s"},
            )
            self._last_response = response
            return response

        except FileNotFoundError:
            response = RuntimeResponse(
                content="",
                tool_calls=[],
                finish_reason=FinishReason.ERROR,
                metadata={"error": "Hermes CLI not found. Install hermes or check PATH."},
            )
            self._last_response = response
            return response

        except Exception as e:
            response = RuntimeResponse(
                content="",
                tool_calls=[],
                finish_reason=FinishReason.ERROR,
                metadata={"error": str(e)},
            )
            self._last_response = response
            return response

    def _parse_response(
        self, stdout: str, stderr: str, returncode: int
    ) -> RuntimeResponse:
        """
        Parse the raw Hermes CLI output into a RuntimeResponse.

        A Hermes response may contain:
        - Normal text content
        - TOOL_CALL: <tool_name> { "arg": "val", ... } directives
        - COMPLETE marker indicating the model is done
        """
        content = stdout
        tool_calls: List[ToolCall] = []

        for match in TOOL_CALL_PATTERN.finditer(stdout):
            tool_name = match.group(1)
            args_str = match.group(2)
            arguments: dict[str, Any] = {}

            for arg_match in ARGUMENT_PATTERN.finditer(args_str):
                key = arg_match.group(1)
                value = arg_match.group(2)
                arguments[key] = value

            tool_calls.append(ToolCall(tool=tool_name, arguments=arguments))

        # Strip tool call lines from the visible content
        if tool_calls:
            content_parts = []
            for line in stdout.split("\n"):
                if not TOOL_CALL_PATTERN.search(line):
                    content_parts.append(line)
            content = "\n".join(content_parts).strip()

        # Determine finish reason
        if returncode != 0 and not content and not tool_calls:
            # Non-zero exit with no usable output
            return RuntimeResponse(
                content="",
                tool_calls=tool_calls,
                finish_reason=FinishReason.ERROR,
                metadata={"stderr": stderr, "returncode": returncode},
            )

        if COMPLETE_MARKER in stdout.upper() or COMPLETE_MARKER in stderr.upper():
            finish_reason = FinishReason.STOP
        elif tool_calls:
            finish_reason = FinishReason.TOOL_CALLS
        elif returncode != 0:
            finish_reason = FinishReason.ERROR
            return RuntimeResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                metadata={"stderr": stderr, "returncode": returncode},
            )
        else:
            finish_reason = FinishReason.STOP

        return RuntimeResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            metadata={"stderr": stderr if stderr else "", "returncode": returncode},
        )

    def capabilities(self) -> dict[str, Any]:
        return {
            "text_generation": True,
            "tool_calls": False,
            "external_tool_execution": False,
            "streaming": False,
            "cancellation": False,
            "adapter": "hermes",
            "model": self.model,
            "provider": self.provider,
            "timeout": self.timeout,
        }

    def cancel(self) -> None:
        """Cancellation is handled by subprocess timeout; no persistent process to kill."""
        pass

    @property
    def default_model(self) -> Optional[str]:
        return self.model

    # Backward-compatibility helpers
    def get_response_text(self) -> str:
        if self._last_response:
            return self._last_response.content
        return ""

    def is_complete(self) -> bool:
        if self._last_response:
            return self._last_response.is_complete
        return False

    def get_pending_tool_calls(self) -> List[ToolCall]:
        if self._last_response:
            return self._last_response.tool_calls
        return []


def create_hermes_runtime(model: Optional[str] = None, provider: Optional[str] = None) -> HermesRuntime:
    return HermesRuntime(model=model, provider=provider)
