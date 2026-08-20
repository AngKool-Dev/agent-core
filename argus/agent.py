"""Argus native agent loop.

Argus owns the complete agentic loop:
  reason → choose tool → execute → observe → reason → ... → finish

This is Argus's own brain, powered by AgentCore primitives but not
controlled by Hermes.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentcore import Agent, AgentConfig, MemoryManager, create_agent
from agentcore.runtimes.base import RuntimeAdapter, ToolCall, ToolResult

from argus.context import ConversationContext, ProjectContext, discover_project_context
from argus.tools import ToolRegistry
from argus.tools.bash import BashTool
from argus.tools.file import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from argus.tools.search import GlobTool, GrepTool


class _InMemoryBackend:
    def __init__(self):
        self._store = []

    def search(self, query, project=None, limit=20):
        return [m for m in self._store if query.lower() in m.get("content", "").lower()]

    def store(self, type, content, project=None, importance=0.5):
        mem = {"id": f"mem-{len(self._store)}", "type": type, "content": content, "project": project}
        self._store.append(mem)
        return mem

    def update(self, memory_id, content):
        for m in self._store:
            if m["id"] == memory_id:
                m["content"] = content
                return m
        return {}

    def list(self, project=None, type=None, limit=50):
        return self._store


@dataclass
class ArgusAgentConfig:
    model: Optional[str] = None
    provider: Optional[str] = None
    max_iterations: int = 10
    max_tool_calls: int = 50
    max_runtime_seconds: int = 300
    enable_verification: bool = True
    run_format_check: bool = True
    run_build_check: bool = True
    run_tests: bool = True


class ArgusAgent:
    def __init__(
        self,
        project_path: Optional[Union[str, Path]] = None,
        config: Optional[ArgusAgentConfig] = None,
        runtime: Optional[RuntimeAdapter] = None,
        memory: Optional[MemoryManager] = None,
    ):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.config = config or ArgusAgentConfig()
        self._runtime = runtime
        self._memory = memory

        self._tool_registry = ToolRegistry()
        self._register_default_tools()

        self._conversation = ConversationContext()
        self._last_result: Optional[Dict[str, Any]] = None
        self._start_time: float = 0.0
        self._iterations: int = 0
        self._tools_used: int = 0

        self._project_context = discover_project_context(str(self.project_path))
        self._conversation.add_system(
            f"You are Argus, an AI coding agent working in project: {self.project_path}"
        )

    def _register_default_tools(self) -> None:
        self._tool_registry.register(ReadFileTool())
        self._tool_registry.register(WriteFileTool())
        self._tool_registry.register(EditFileTool())
        self._tool_registry.register(ListDirTool())
        self._tool_registry.register(BashTool())
        self._tool_registry.register(GrepTool())
        self._tool_registry.register(GlobTool())

    def execute(self, request: str) -> Dict[str, Any]:
        self._start_time = time.time()
        self._iterations = 0
        self._tools_used = 0
        self._conversation.add_user(request)

        result = {
            "request": request,
            "task_id": f"task-{int(self._start_time)}",
            "status": "RUNNING",
            "iterations": 0,
            "tools_used": 0,
            "tool_results": [],
            "final_response": "",
            "success": False,
        }

        try:
            plan = self._plan(request)
            result["plan"] = [s.to_dict() for s in plan]

            execution = self._run_loop(plan, request)
            result.update(execution)

            if result["status"] == "RUNNING":
                result["status"] = "COMPLETED"
                result["success"] = True

        except KeyboardInterrupt:
            result["status"] = "INTERRUPTED"
        except Exception as e:
            result["status"] = "FAILED"
            result["error"] = str(e)

        result["iterations"] = self._iterations
        result["tools_used"] = self._tools_used
        self._last_result = result

        final = result.get("final_response") or result.get("status", "Done")
        self._conversation.add_assistant(final, result=result)
        return result

    def _plan(self, request: str) -> List["PlanStep"]:
        request_lower = request.lower()
        if any(word in request_lower for word in ["fix", "crash", "bug", "error", "fail"]):
            return self._make_plan("bug_fix", request)
        if any(word in request_lower for word in ["implement", "add", "create", "new"]):
            return self._make_plan("feature", request)
        if any(word in request_lower for word in ["refactor", "simplify", "clean"]):
            return self._make_plan("refactor", request)
        return self._make_plan("investigate", request)

    def _make_plan(self, kind: str, request: str) -> List["PlanStep"]:
        if kind == "bug_fix":
            return [
                PlanStep(action="investigate", description="Investigate the bug"),
                PlanStep(action="implement", description="Implement the fix"),
                PlanStep(action="verify", description="Verify the fix"),
            ]
        elif kind == "feature":
            return [
                PlanStep(action="investigate", description="Explore relevant code"),
                PlanStep(action="implement", description="Implement the feature"),
                PlanStep(action="verify", description="Verify implementation"),
            ]
        elif kind == "refactor":
            return [
                PlanStep(action="investigate", description="Analyze current structure"),
                PlanStep(action="implement", description="Apply refactoring"),
                PlanStep(action="verify", description="Run tests and checks"),
            ]
        return [
            PlanStep(action="investigate", description="Explore the codebase"),
            PlanStep(action="summarize", description="Summarize findings"),
        ]

    def _run_loop(self, plan: List["PlanStep"], request: str) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "status": "RUNNING",
            "tool_results": [],
            "final_response": "",
        }

        plan_steps = list(plan)
        completed_steps = set()

        while self._iterations < self.config.max_iterations:
            elapsed = time.time() - self._start_time
            if elapsed > self.config.max_runtime_seconds:
                results["status"] = "TIMEOUT"
                break

            if self._tools_used >= self.config.max_tool_calls:
                results["status"] = "TOOL_LIMIT"
                break

            context = self._build_context(request)

            try:
                if self._runtime:
                    runtime_response = self._runtime.respond(context)
                else:
                    runtime_response = self._default_reason(context, request)
            except Exception as e:
                results["status"] = "RUNTIME_ERROR"
                results["error"] = str(e)
                break

            if runtime_response.get("complete"):
                results["status"] = "COMPLETED"
                results["final_response"] = runtime_response.get("response", "Done")
                break

            tool_calls = runtime_response.get("tool_calls", [])
            if not tool_calls and runtime_response.get("response"):
                results["final_response"] = runtime_response["response"]
                self._iterations += 1
                break

            for tc in tool_calls:
                if self._tools_used >= self.config.max_tool_calls:
                    break
                tool_result = self._execute_tool_call(tc)
                results["tool_results"].append(tool_result.to_dict())

            next_step = self._next_step(plan_steps, completed_steps)
            if not next_step:
                results["status"] = "COMPLETED"
                results["final_response"] = results.get("final_response") or "Task completed"
                break

            self._iterations += 1

        return results

    def _build_context(self, request: str) -> Dict[str, Any]:
        return {
            "user_request": request,
            "project_context": self._project_context.to_dict(),
            "conversation": self._conversation.to_list(),
            "available_tools": self._tool_registry.list_tools(),
            "instructions": [
                "You are Argus, an AI coding agent.",
                "Work iteratively: analyze, act, observe, refine.",
                "Use tools to explore and modify code.",
                "Always verify changes with tests when possible.",
            ],
        }

    def _default_reason(self, context: Dict[str, Any], request: str) -> Dict[str, Any]:
        conversation = context.get("conversation", [])
        last_user = next((m for m in reversed(conversation) if m["role"] == "user"), None)
        user_text = (last_user or {}).get("content", request).lower()

        if any(word in user_text for word in ["read", "show", "find", "search", "grep"]):
            return {
                "complete": False,
                "response": "Searching...",
                "tool_calls": [
                    ToolCall(tool="grep", arguments={"pattern": request, "path": str(self.project_path)}, call_id="1").to_dict()
                ],
            }

        if any(word in user_text for word in ["write", "create", "generate"]):
            return {
                "complete": False,
                "response": "Writing...",
                "tool_calls": [
                    ToolCall(tool="list_dir", arguments={"path": str(self.project_path)}, call_id="1").to_dict()
                ],
            }

        if any(word in user_text for word in ["fix", "bug", "error", "crash"]):
            return {
                "complete": False,
                "response": "Investigating...",
                "tool_calls": [
                    ToolCall(tool="list_dir", arguments={"path": str(self.project_path)}, call_id="1").to_dict()
                ],
            }

        return {
            "complete": True,
            "response": f"Processed request: {request}",
            "tool_calls": [],
        }

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        self._tools_used += 1
        result = self._tool_registry.execute(tool_call.tool, **tool_call.arguments)
        return result

    def _next_step(self, plan: List["PlanStep"], completed: set) -> Optional["PlanStep"]:
        for step in plan:
            if step.action not in completed:
                completed.add(step.action)
                return step
        return None

    def status(self) -> Dict[str, Any]:
        if not self._last_result:
            return {"status": "idle"}
        return {
            "status": self._last_result.get("status", "unknown"),
            "task_id": self._last_result.get("task_id"),
            "tools_used": self._last_result.get("tools_used", 0),
            "iterations": self._last_result.get("iterations", 0),
            "success": self._last_result.get("success", False),
        }

    def last_result(self) -> Optional[Dict[str, Any]]:
        return self._last_result

    def switch_project(self, project_path: Union[str, Path]) -> None:
        self.project_path = Path(project_path)
        self._project_context = discover_project_context(str(self.project_path))
        self._conversation.clear()
        self._last_result = None


@dataclass
class PlanStep:
    action: str
    description: str
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "description": self.description,
            "completed": self.completed,
        }
