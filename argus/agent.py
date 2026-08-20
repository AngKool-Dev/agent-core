"""Argus native agent loop.

Argus owns the complete agentic loop:
  reason → choose tool → execute → observe → reason → ... → finish

This is Argus's own brain, powered by AgentCore primitives but not
controlled by Hermes.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from agentcore import Agent, AgentConfig, MemoryManager, create_agent
from agentcore.runtimes.base import RuntimeAdapter, ToolCall, ToolResult

from argus.context import ConversationContext, ProjectContext, ProjectProfile, discover_project_context
from argus.memory import ArgusMemory
from argus.model import ModelProvider, build_messages, parse_model_output
from argus.skills import Skill, SkillRegistry, SkillRouter
from argus.tools import ToolRegistry
from argus.tools.bash import BashTool
from argus.tools.file import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from argus.tools.git import GitAddTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool, GitWorkflowTool
from argus.tools.memory import MemoryAddTool, MemorySearchTool, set_agent as set_memory_agent
from argus.tools.search import GlobTool, GrepTool


StatusCallback = Callable[[str], None]


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
    max_consecutive_failures: int = 3
    max_no_progress: int = 3
    enable_verification: bool = True
    run_format_check: bool = True
    run_build_check: bool = True
    run_tests: bool = True
    workspace_boundaries_enabled: bool = True
    commit_approval_callback: Optional[Callable[[str], bool]] = None


class ArgusAgent:
    def __init__(
        self,
        project_path: Optional[Union[str, Path]] = None,
        config: Optional[ArgusAgentConfig] = None,
        runtime: Optional[RuntimeAdapter] = None,
        memory: Optional[MemoryManager] = None,
        status_callback: Optional[StatusCallback] = None,
        model: Optional[ModelProvider] = None,
        skill_paths: Optional[List[Path]] = None,
        commit_approval_callback: Optional[Callable[[str], bool]] = None,
    ):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.config = config or ArgusAgentConfig()
        if commit_approval_callback is not None:
            self.config.commit_approval_callback = commit_approval_callback
        self._runtime = runtime
        self._memory_manager = memory
        self._status_callback = status_callback
        self._model = model

        self._tool_registry = ToolRegistry()
        self._register_default_tools()

        self.memory = ArgusMemory(memory_manager=memory, project_path=self.project_path)
        set_memory_agent(self)

        self._skill_registry = SkillRegistry(skill_paths)
        self._skill_router = SkillRouter(self._skill_registry)
        self._active_skills: List[Skill] = []

        self._conversation = ConversationContext()
        self._last_result: Optional[Dict[str, Any]] = None
        self._start_time: float = 0.0
        self._iterations: int = 0
        self._tools_used: int = 0
        self._consecutive_failures: int = 0
        self._no_progress_count: int = 0
        self._last_tool_calls: List[str] = []
        self._cancelled: bool = False

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
        self._tool_registry.register(GitStatusTool())
        self._tool_registry.register(GitDiffTool())
        self._tool_registry.register(GitLogTool())
        self._tool_registry.register(GitAddTool())
        self._tool_registry.register(GitCommitTool())
        self._tool_registry.register(GitWorkflowTool())
        self._tool_registry.register(MemoryAddTool())
        self._tool_registry.register(MemorySearchTool())

    def _status(self, message: str) -> None:
        if self._status_callback:
            self._status_callback(message)

    def discover_skills(self, paths: Optional[List[Path]] = None) -> List[Skill]:
        return self._skill_registry.discover(paths)

    def route_skills(self, request: str) -> List[Skill]:
        self._skill_router = SkillRouter(self._skill_registry)
        self._active_skills = self._skill_router.route(request, self._project_context.to_dict())
        return self._active_skills

    def active_skills(self) -> List[Skill]:
        return list(self._active_skills)

    def execute(self, request: str) -> Dict[str, Any]:
        self._start_time = time.time()
        self._iterations = 0
        self._tools_used = 0
        self._consecutive_failures = 0
        self._no_progress_count = 0
        self._last_tool_calls = []
        self._cancelled = False
        self._last_result = None
        self._conversation.add_user(request)

        self.route_skills(request)

        result = {
            "request": request,
            "task_id": f"task-{int(self._start_time)}",
            "status": "RUNNING",
            "iterations": 0,
            "tools_used": 0,
            "tool_results": [],
            "observations": [],
            "skills": [s.name for s in self._active_skills],
            "final_response": "",
            "success": False,
            "failure_reason": None,
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
            result["status"] = "CANCELLED"
            result["failure_reason"] = "user_cancellation"
        except Exception as e:
            result["status"] = "FAILED"
            result["failure_reason"] = "unexpected_error"
            result["error"] = str(e)

        result["iterations"] = self._iterations
        result["tools_used"] = self._tools_used
        self._last_result = result

        final = result.get("final_response") or result.get("status", "Done")
        self._conversation.add_assistant(final, result=result)
        return result

    def cancel(self) -> None:
        self._cancelled = True

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
            "observations": [],
            "final_response": "",
            "failure_reason": None,
        }

        plan_steps = list(plan)
        completed_steps = set()
        current_step = self._next_step(plan_steps, completed_steps)

        while self._iterations < self.config.max_iterations:
            elapsed = time.time() - self._start_time
            if elapsed > self.config.max_runtime_seconds:
                results["status"] = "TIMEOUT"
                results["failure_reason"] = "timeout"
                break

            if self._tools_used >= self.config.max_tool_calls:
                results["status"] = "TOOL_LIMIT"
                results["failure_reason"] = "tool_limit"
                break

            if self._consecutive_failures >= self.config.max_consecutive_failures:
                results["status"] = "FAILED"
                results["failure_reason"] = "consecutive_tool_failures"
                results["final_response"] = f"Stopped after {self._consecutive_failures} consecutive tool failures"
                break

            if self._cancelled:
                results["status"] = "CANCELLED"
                results["failure_reason"] = "user_cancellation"
                results["final_response"] = "Task was cancelled by user"
                break

            context = self._build_context(request, results)

            try:
                if self._model:
                    runtime_response = self._model_reason(context, request)
                elif self._runtime:
                    runtime_response = self._runtime.respond(context)
                else:
                    runtime_response = self._default_reason(context, request, results)
            except Exception as e:
                results["status"] = "RUNTIME_ERROR"
                results["failure_reason"] = "model_error"
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

            if not tool_calls:
                results["status"] = "COMPLETED"
                results["final_response"] = "No further actions needed"
                break

            batch_results = []
            for tc in tool_calls:
                if self._tools_used >= self.config.max_tool_calls:
                    break
                tool_result = self._execute_tool_call(tc)
                batch_results.append(tool_result)
                results["tool_results"].append(tool_result.to_dict())

            observation = self._observe_batch(batch_results, current_step)
            results["observations"].append(observation)
            self._status(f"Observed: {observation[:120]}")

            failures = [r for r in batch_results if not r.success]
            if failures:
                self._consecutive_failures += 1
            else:
                self._consecutive_failures = 0

            current_calls = [r.tool for r in batch_results]
            if current_calls == self._last_tool_calls:
                self._no_progress_count += 1
            else:
                self._no_progress_count = 0
            self._last_tool_calls = current_calls

            if self._no_progress_count >= self.config.max_no_progress:
                results["status"] = "FAILED"
                results["failure_reason"] = "no_progress"
                results["final_response"] = "Stopped due to repeated identical tool calls"
                break

            if self._should_stop_after_observation(batch_results, current_step):
                results["status"] = "COMPLETED"
                results["final_response"] = results.get("final_response") or "Task completed"
                break

            current_step = self._next_step(plan_steps, completed_steps)
            if not current_step and all(s.completed for s in plan_steps):
                results["status"] = "COMPLETED"
                results["final_response"] = results.get("final_response") or "Task completed"
                break

            self._iterations += 1

        return results

    def _build_context(self, request: str, results: Dict[str, Any]) -> Dict[str, Any]:
        recent_observations = results.get("observations", [])[-3:]
        active_skills = getattr(self, "_active_skills", [])
        skill_instructions = "\n\n".join(s.to_context() for s in active_skills)
        memory_context = self.memory.retrieve_relevant(request)
        return {
            "user_request": request,
            "project_context": self._project_context.to_dict(),
            "project_profile": self._project_context,
            "conversation": self._conversation.to_list(),
            "available_tools": self._tool_registry.list_tools(),
            "recent_tool_results": [
                tr.to_dict() if hasattr(tr, "to_dict") else tr
                for tr in results.get("tool_results", [])[-5:]
            ],
            "recent_observations": recent_observations,
            "current_step": results.get("plan", [{}])[0].get("action", "investigate"),
            "active_skills": [s.to_dict() for s in active_skills],
            "skill_instructions": skill_instructions,
            "memory_context": memory_context,
            "instructions": [
                "You are Argus, an AI coding agent.",
                "Work iteratively: analyze, act, observe, refine.",
                "Use tools to explore and modify code.",
                "After observing results, decide whether to continue, retry, or finish.",
                "Always verify changes with tests when possible.",
            ],
        }

    def _model_reason(self, context: Dict[str, Any], request: str) -> Dict[str, Any]:
        if not self._model:
            return self._default_reason(context, request, {})

        messages = build_messages(
            user_request=request,
            conversation=context.get("conversation", []),
            project_context=context.get("project_context", {}),
            project_profile=context.get("project_profile"),
            available_tools=context.get("available_tools", []),
            recent_observations=context.get("recent_observations", []),
            current_step=context.get("current_step", "investigate"),
            active_skills=context.get("active_skills"),
            skill_instructions=context.get("skill_instructions", ""),
            memory_context=context.get("memory_context", ""),
        )

        model_name = self.config.model or "gpt-4o"
        response = self._model.complete(
            messages=messages,
            model=model_name,
            tools=context.get("available_tools", []),
        )

        text, tool_calls = parse_model_output(response.content)

        if tool_calls:
            return {
                "complete": False,
                "response": text or "Using tools...",
                "tool_calls": [tc.__dict__ for tc in tool_calls],
            }

        return {
            "complete": True,
            "response": text or response.content or "Done",
            "tool_calls": [],
        }

    def _observe_batch(self, tool_results: List[ToolResult], step: Optional["PlanStep"]) -> str:
        if not tool_results:
            return "No tools executed"

        successes = [r for r in tool_results if r.success]
        failures = [r for r in tool_results if not r.success]

        parts = []
        if step:
            parts.append(f"Step '{step.action}': ")
        parts.append(f"{len(successes)} succeeded, {len(failures)} failed")

        if failures:
            errors = [r.error for r in failures[:3] if r.error]
            if errors:
                parts.append(f"Errors: {'; '.join(errors)}")

        output_preview = ""
        for r in successes:
            if r.output:
                output_preview = r.output[:200]
                break

        if output_preview:
            parts.append(f"Output preview: {output_preview}")

        return ". ".join(parts)

    def _should_stop_after_observation(
        self, tool_results: List[ToolResult], step: Optional["PlanStep"]
    ) -> bool:
        current_calls = [r.tool for r in tool_results]
        recent_calls = getattr(self, "_recent_tool_calls", [])
        self._recent_tool_calls = (recent_calls + current_calls)[-20:]

        if not tool_results:
            return False

        if len(self._recent_tool_calls) >= 8:
            last_eight = self._recent_tool_calls[-8:]
            if len(set(last_eight)) == 1:
                return True

        failures = [r for r in tool_results if not r.success]
        if failures and step and step.action == "verify":
            return True

        if step and step.action == "investigate":
            return any(r.tool == "read_file" and r.success for r in tool_results)

        return False

    def _default_reason(self, context: Dict[str, Any], request: str, results: Dict[str, Any]) -> Dict[str, Any]:
        recent_tools = [tr.get("tool") for tr in context.get("recent_tool_results", [])]
        recent_observations = context.get("recent_observations", [])
        user_text = request.lower()

        if "investigate" in context.get("current_step", ""):
            if "list_dir" not in recent_tools:
                return {
                    "complete": False,
                    "response": "Exploring project structure...",
                    "tool_calls": [
                        ToolCall(tool="list_dir", arguments={"path": str(self.project_path), "workspace": str(self.project_path)}, thought="").to_dict()
                    ],
                }
            if "read_file" not in recent_tools:
                readme = context.get("project_context", {}).get("readme")
                if readme:
                    return {
                        "complete": False,
                        "response": "Reading README...",
                        "tool_calls": [
                            ToolCall(tool="read_file", arguments={"path": str(self.project_path / "README.md")}, thought="").to_dict()
                        ],
                    }
            return {"complete": False, "response": "Investigation complete", "tool_calls": []}

        if "implement" in context.get("current_step", ""):
            if "grep" not in recent_tools and any(word in user_text for word in ["fix", "bug", "error"]):
                return {
                    "complete": False,
                    "response": "Searching for error patterns...",
                    "tool_calls": [
                        ToolCall(tool="grep", arguments={"pattern": "panic|crash|error|traceback", "path": str(self.project_path)}, thought="").to_dict()
                    ],
                }
            if "read_file" not in recent_tools:
                return {
                    "complete": False,
                    "response": "Reading target file...",
                    "tool_calls": [
                        ToolCall(tool="list_dir", arguments={"path": str(self.project_path), "workspace": str(self.project_path)}, thought="").to_dict()
                    ],
                }
            return {
                "complete": False,
                "response": "Ready to apply changes",
                "tool_calls": [],
            }

        if "verify" in context.get("current_step", ""):
            if "bash" not in recent_tools:
                return {
                    "complete": False,
                    "response": "Running tests...",
                    "tool_calls": [
                        ToolCall(tool="bash", arguments={"command": "pytest || cargo test || npm test", "cwd": str(self.project_path)}, thought="").to_dict()
                    ],
                }
            return {"complete": True, "response": "Verification complete", "tool_calls": []}

        if any(word in user_text for word in ["fix", "crash", "bug", "error", "fail"]):
            return {
                "complete": False,
                "response": "Investigating bug...",
                "tool_calls": [
                            ToolCall(tool="list_dir", arguments={"path": str(self.project_path), "workspace": str(self.project_path)}, thought="").to_dict()
                ],
            }

        return {"complete": True, "response": f"Processed request: {request}", "tool_calls": []}

    def _execute_tool_call(self, tool_call) -> ToolResult:
        if isinstance(tool_call, dict):
            tool_name = tool_call.get("tool") or tool_call.get("tool_name") or ""
            arguments = tool_call.get("arguments", {})
        else:
            tool_name = getattr(tool_call, "tool", "")
            arguments = getattr(tool_call, "arguments", {})

        if not isinstance(arguments, dict):
            arguments = {}

        if self.config.workspace_boundaries_enabled and tool_name in ("read_file", "write_file", "edit_file", "list_dir", "grep", "glob", "git_status", "git_diff", "git_log", "git_add", "git_commit"):
            arguments.setdefault("workspace", str(self.project_path))

        self._tools_used += 1
        self._status(f"Running {tool_name}...")
        result = self._tool_registry.execute(tool_name, **arguments)
        status = "success" if result.success else "failed"
        self._status(f"Tool {tool_name} {status}")

        if self._handle_workflow_approval(tool_name, result):
            return result

        return result

    def _handle_workflow_approval(self, tool_name: str, result: ToolResult) -> bool:
        if tool_name != "git_workflow":
            return False

        metadata = result.metadata or {}
        if not metadata.get("needs_approval"):
            return False

        approval_message = metadata.get("approval_message", "")
        if not approval_message or not self.config.commit_approval_callback:
            return False

        approved = self.config.commit_approval_callback(approval_message)
        tool = self._tool_registry.get("git_workflow")
        if tool and hasattr(tool, "_workflows"):
            project_path = str(self.project_path)
            if project_path in tool._workflows:
                workflow = tool._workflows[project_path]
                commit_message = metadata.get("commit_message", "")
                if not commit_message:
                    diff_info = metadata.get("diff", {})
                    relevant = metadata.get("relevant", [])
                    if relevant:
                        commit_message = f"Update {', '.join(relevant[:3])}"
                    else:
                        commit_message = "Apply changes"
                workflow.set_approved(approved, commit_message)

        return approved

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
