import re
import subprocess
import threading
from typing import Any

from .base import (
    FinishReason,
    HermesAPI,
    RuntimeAdapter,
    RuntimeResponse,
    ToolCall,
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

    def __init__(self, model: str | None = None, provider: str | None = None, timeout: int = 300):
        self.model = model
        self.provider = provider
        self.timeout = timeout
        self._last_response: RuntimeResponse | None = None
        self._active_process: subprocess.Popen | None = None
        self._process_lock = threading.Lock()
        self._cancelled = False

    def respond(self, context: dict[str, Any]) -> RuntimeResponse:
        """Send a context to the Hermes CLI and return a structured response."""
        full_prompt = HermesAPI.build_prompt(context)

        hermes_args = ["hermes", "-z"]
        if self.model:
            hermes_args.extend(["-m", self.model])
        if self.provider:
            hermes_args.extend(["--provider", self.provider])

        self._cancelled = False
        try:
            process = subprocess.Popen(
                [*hermes_args, full_prompt],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with self._process_lock:
                self._active_process = process
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                returncode = process.returncode
            finally:
                with self._process_lock:
                    if self._active_process is process:
                        self._active_process = None
        except subprocess.TimeoutExpired:
            self._cancel_in_flight()
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

        if self._cancelled:
            response = RuntimeResponse(
                content="",
                tool_calls=[],
                finish_reason=FinishReason.CANCELLED,
                metadata={"stderr": "Hermes call was cancelled"},
            )
            self._last_response = response
            return response

        response_text = stdout.strip() if stdout else ""
        stderr_text = stderr.strip() if stderr else ""

        parsed = self._parse_response(response_text, stderr_text, returncode)
        self._last_response = parsed
        return parsed

    def cancel(self) -> None:
        """Terminate the in-flight Hermes subprocess if one is running."""
        self._cancelled = True
        self._cancel_in_flight()

    def _cancel_in_flight(self) -> None:
        """Terminate the active subprocess if one is running."""
        with self._process_lock:
            process = self._active_process
            if process is None:
                return
            self._active_process = None

        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
        except Exception:
            pass

    def _parse_response(self, stdout: str, stderr: str, returncode: int) -> RuntimeResponse:
        """
        Parse the raw Hermes CLI output into a RuntimeResponse.

        A Hermes response may contain:
        - Normal text content
        - TOOL_CALL: <tool_name> { "arg": "val", ... } directives
        - COMPLETE marker indicating the model is done
        """
        content = stdout
        tool_calls: list[ToolCall] = []

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
            "cancellation": True,
            "adapter": "hermes",
            "model": self.model,
            "provider": self.provider,
            "timeout": self.timeout,
        }

    @property
    def default_model(self) -> str | None:
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

    def get_pending_tool_calls(self) -> list[ToolCall]:
        if self._last_response:
            return self._last_response.tool_calls
        return []


def create_hermes_runtime(model: str | None = None, provider: str | None = None) -> HermesRuntime:
    return HermesRuntime(model=model, provider=provider)
