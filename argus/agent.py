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
from argus.engineering import (
    EngineeringPhase,
    EngineeringTaskState,
    EngineeringLoopConfig,
    EvidenceCategory,
    should_enter_engineering_loop,
    select_verification_commands,
    extract_modified_files,
    is_trivial_request,
)


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
    enable_engineering_loop: bool = False
    max_repair_attempts: int = 2
    max_plan_revisions: int = 2


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
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.config = config or ArgusAgentConfig()
        if commit_approval_callback is not None:
            self.config.commit_approval_callback = commit_approval_callback
        self._runtime = runtime
        self._memory_manager = memory
        self._status_callback = status_callback
        self._model = model

        self._tool_registry = tool_registry or ToolRegistry()
        if not tool_registry:
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
        self._current_step_action: str = "investigate"
        self._engineering_state: Optional[EngineeringTaskState] = None

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
        self._engineering_state = None
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

            if self.config.enable_engineering_loop and should_enter_engineering_loop(request, self._tool_results_to_list(result.get("tool_results", []))):
                engineering_result = self._run_engineering_loop(request, result)
                result.update(engineering_result)

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
        if current_step:
            self._current_step_action = current_step.action

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
            if current_step:
                self._current_step_action = current_step.action
            if not current_step and all(s.completed for s in plan_steps):
                results["status"] = "COMPLETED"
                results["final_response"] = results.get("final_response") or "Task completed"
                break

            self._iterations += 1

        return {**results, "completed_steps": list(completed_steps)}

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
            "current_step": self._current_step_action or "investigate",
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

        try:
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
                request=request,
            )
        except Exception:
            import logging
            logging.getLogger("argus").debug("Model unavailable, using built-in default reasoner")
            return self._default_reason(context, request, {})

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

        if "summarize" in context.get("current_step", ""):
            return {
                "complete": True,
                "response": "Task completed.",
                "tool_calls": [],
            }

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
            if "write_file" not in recent_tools and "create a file" in user_text:
                lines = self._extract_file_creation_request(user_text, request)
                if lines:
                    return {
                        "complete": False,
                        "response": "Creating file...",
                        "tool_calls": lines,
                    }
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

    def _extract_file_creation_request(self, user_text: str, request: str) -> List[Dict[str, Any]]:
        """Extract file creation instructions from a natural language request."""
        import re
        lines = []

        pattern = r'create\s+(?:a\s+)?file\s+(?:called|named|named)\s+([^\s]+)'
        match = re.search(pattern, user_text)
        if not match:
            pattern = r'create\s+([^\s]+\.[^\s]+)'
            match = re.search(pattern, user_text)

        if match:
            filename = match.group(1)
            if not filename.endswith('.py'):
                filename = filename

            file_path = str(self.project_path / filename)

            content_match = re.search(r'containing\s+(?:a\s+)?(?:program|script|Python\s+program)\s+(?:that\s+)?(.+?)(?:\.|$)', request, re.IGNORECASE | re.DOTALL)
            if content_match:
                content_desc = content_match.group(1).strip()
                if "prints" in content_desc:
                    print_match = re.search(r'prints\s+(.+)', content_desc, re.IGNORECASE)
                    if print_match:
                        print_text = print_match.group(1).strip().rstrip('.').strip()
                        content = f'print("{print_text}")\n'
                    else:
                        content = f'"""{filename}"""\n{content_desc}\n'
                else:
                    content = f'"""{filename}"""\n{content_desc}\n'
            else:
                lines_match = re.findall(r'-\s*(.+)', request)
                if lines_match:
                    content = '\n'.join(lines_match) + '\n'
                else:
                    content = f'"""{filename}"""\n'

            lines.append(ToolCall(
                tool="write_file",
                arguments={"path": file_path, "content": content},
                thought="",
            ).to_dict())

        return lines

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

    def _tool_results_to_list(self, tool_results: List[Dict[str, Any]]) -> List[ToolResult]:
        from agentcore.runtimes.base import ToolResult as TR
        result = []
        for tr in tool_results:
            if isinstance(tr, TR):
                result.append(tr)
            elif isinstance(tr, dict):
                result.append(TR(
                    tool=tr.get("tool", ""),
                    success=tr.get("success", False),
                    stdout=tr.get("stdout", ""),
                    stderr=tr.get("stderr", ""),
                    exit_code=tr.get("exit_code", 0),
                    duration=tr.get("duration", 0.0),
                    error=tr.get("error", ""),
                ))
        return result

    def _run_engineering_loop(self, request: str, base_result: Dict[str, Any]) -> Dict[str, Any]:
        eng_config = EngineeringLoopConfig(
            enabled=True,
            max_repair_attempts=self.config.max_repair_attempts,
            max_plan_revisions=getattr(self.config, "max_plan_revisions", 2),
            run_verification=self.config.enable_verification,
            run_format_check=self.config.run_format_check,
            run_build_check=self.config.run_build_check,
            run_tests=self.config.run_tests,
        )

        self._engineering_state = EngineeringTaskState(goal=request)
        state = self._engineering_state
        tool_results = base_result.get("tool_results", [])

        state.phase = EngineeringPhase.UNDERSTAND
        self._status(f"Phase: UNDERSTAND")

        state.phase = EngineeringPhase.INVESTIGATE
        self._status(f"Phase: INVESTIGATE")
        if not state.investigation_findings:
            self._run_investigation(request)

        state.phase = EngineeringPhase.PLAN
        self._status(f"Phase: PLAN")
        state.plan_steps = base_result.get("plan", [])
        state.modified_files = extract_modified_files(tool_results)
        state.completed_steps = list(base_result.get("completed_steps", []))

        state.phase = EngineeringPhase.EXECUTE
        self._status(f"Phase: EXECUTE")

        existing_tool_results = base_result.get("tool_results", [])
        self._extract_execution_evidence(state, existing_tool_results)

        contradiction_during_execution = self._check_execution_contradictions(state)
        if not contradiction_during_execution and existing_tool_results and self._model:
            contradiction_during_execution = self._model_evaluate_contradiction(state)
        if contradiction_during_execution and contradiction_during_execution.get("replan", False):
            state.add_evidence(
                EngineeringPhase.EXECUTE.value,
                command="",
                success=False,
                output_summary=f"Contradictory evidence detected during execution: {contradiction_during_execution.get('reason', '')}",
                category=EvidenceCategory.IMPLEMENTATION_DIFFERS.value,
            )
            self._status("Contradictory evidence detected during execution")

            if state.plan_revision_count < eng_config.max_plan_revisions:
                state.phase = EngineeringPhase.REPLAN
                self._status(f"Phase: REPLAN (revision {state.plan_revision_count + 1}/{eng_config.max_plan_revisions})")
                replan_summary = self._run_model_replan(state)
                state.add_evidence(EngineeringPhase.REPLAN.value, command="", success=True, output_summary=replan_summary)

                state.phase = EngineeringPhase.EXECUTE
                self._status(f"Phase: EXECUTE (revised plan)")
                execution_summary = self._execute_revised_plan(state)
                state.add_evidence(EngineeringPhase.EXECUTE.value, command="", success=True, output_summary=execution_summary)

                if "Contradiction detected" in execution_summary or "failed" in execution_summary.lower():
                    if state.plan_revision_count < eng_config.max_plan_revisions:
                        state.phase = EngineeringPhase.REPLAN
                        self._status(f"Phase: REPLAN (revision {state.plan_revision_count + 1}/{eng_config.max_plan_revisions})")
                        replan_summary = self._run_model_replan(state)
                        state.add_evidence(EngineeringPhase.REPLAN.value, command="", success=True, output_summary=replan_summary)

                        state.phase = EngineeringPhase.EXECUTE
                        self._status(f"Phase: EXECUTE (revised plan)")
                        execution_summary = self._execute_revised_plan(state)
                        state.add_evidence(EngineeringPhase.EXECUTE.value, command="", success=True, output_summary=execution_summary)
                    else:
                        state.final_status = "FAILED"
                        state.add_evidence(
                            EngineeringPhase.EXECUTE.value,
                            success=False,
                            output_summary="Max plan revisions reached during execution",
                        )
                        return self._engineering_result(base_result)
            else:
                state.final_status = "FAILED"
                state.add_evidence(
                    EngineeringPhase.EXECUTE.value,
                    success=False,
                    output_summary="Max plan revisions reached, contradiction unresolved",
                )
                return self._engineering_result(base_result)
        elif existing_tool_results:
            state.add_evidence(EngineeringPhase.EXECUTE.value, success=True, output_summary="Execution completed, no contradictions detected")

        state.phase = EngineeringPhase.VERIFY
        self._status(f"Phase: VERIFY")

        if not state.modified_files:
            state.add_evidence(EngineeringPhase.VERIFY.value, command="", success=True, output_summary="No code modifications detected")
            state.phase = EngineeringPhase.REVIEW
            self._status(f"Phase: REVIEW")
            state.review_findings.append("No code changes to review")
            state.phase = EngineeringPhase.FINALIZE
            self._status(f"Phase: FINALIZE")
            state.final_status = "COMPLETED"
            return self._engineering_result(base_result)

        verification_commands = select_verification_commands(self._project_context, eng_config)
        if not verification_commands:
            state.add_evidence(EngineeringPhase.VERIFY.value, command="", success=True, output_summary="No verification commands available for this project")
            state.verification_results.append({"command": "", "success": True, "summary": "No verification commands available"})
        else:
            for cmd in verification_commands:
                if self._cancelled:
                    break
                self._status(f"Running {cmd}...")
                success, summary = self._run_verification_command(cmd, state)
                state.add_evidence(EngineeringPhase.VERIFY.value, command=cmd, success=success, output_summary=summary)
                state.verification_results.append({"command": cmd, "success": success, "summary": summary})
                if not success:
                    break

        verification_passed = all(v.get("success", True) for v in state.verification_results)

        if not verification_passed:
            state.phase = EngineeringPhase.REVIEW
            self._status(f"Phase: REVIEW")
            state.review_findings.append("Verification failed")
            self._status("Verification failed, checking if replanning is needed")

            replanned = False
            if self._should_replan(state):
                state.phase = EngineeringPhase.REPLAN
                self._status(f"Phase: REPLAN (revision {state.plan_revision_count + 1}/{eng_config.max_plan_revisions})")
                replan_summary = self._run_model_replan(state)
                state.add_evidence(EngineeringPhase.REPLAN.value, command="", success=True, output_summary=replan_summary)
                if state.plan_revision_count < eng_config.max_plan_revisions:
                    state.phase = EngineeringPhase.EXECUTE
                    self._status(f"Phase: EXECUTE (revised plan)")
                    state.phase = EngineeringPhase.VERIFY
                    self._status(f"Phase: VERIFY (after replan)")
                    verification_commands = select_verification_commands(self._project_context, eng_config)
                    if verification_commands:
                        all_passed = True
                        for cmd in verification_commands:
                            if self._cancelled:
                                all_passed = False
                                break
                            self._status(f"Running {cmd}...")
                            success, summary = self._run_verification_command(cmd, state)
                            state.add_evidence(EngineeringPhase.VERIFY.value, command=cmd, success=success, output_summary=summary)
                            state.verification_results.append({"command": cmd, "success": success, "summary": summary})
                            if not success:
                                all_passed = False
                                break
                        verification_passed = all_passed
                    else:
                        verification_passed = True
                    replanned = verification_passed

            if not replanned:
                self._status("Verification failed, entering repair loop")

                verification_failure = {
                    "command": state.verification_results[-1].get("command", "") if state.verification_results else "",
                    "summary": state.verification_results[-1].get("summary", "") if state.verification_results else "",
                }

                for attempt in range(eng_config.max_repair_attempts):
                    state.repair_attempts = attempt + 1
                    state.phase = EngineeringPhase.REPAIR
                    self._status(f"Phase: REPAIR (attempt {attempt + 1}/{eng_config.max_repair_attempts})")

                    repair_summary = self._run_model_repair(state, verification_failure)
                    state.add_evidence(EngineeringPhase.REPAIR.value, command="", success=True, output_summary=repair_summary)

                    state.phase = EngineeringPhase.VERIFY
                    self._status(f"Phase: VERIFY (after repair {attempt + 1})")
                    verification_commands = select_verification_commands(self._project_context, eng_config)
                    if not verification_commands:
                        state.add_evidence(EngineeringPhase.VERIFY.value, command="", success=True, output_summary="No verification commands available")
                        verification_passed = True
                        break

                    all_passed = True
                    for cmd in verification_commands:
                        if self._cancelled:
                            all_passed = False
                            break
                        self._status(f"Running {cmd}...")
                        success, summary = self._run_verification_command(cmd, state)
                        state.add_evidence(EngineeringPhase.VERIFY.value, command=cmd, success=success, output_summary=summary)
                        state.verification_results.append({"command": cmd, "success": success, "summary": summary})
                        if not success:
                            all_passed = False
                            break

                    verification_passed = all_passed
                    if verification_passed:
                        self._status("Verification passed after repair")
                        break

                if not verification_passed:
                    state.final_status = "FAILED"
                    state.add_evidence(EngineeringPhase.VERIFY.value, command="", success=False, output_summary="All repair attempts exhausted")
                    return self._engineering_result(base_result)

        state.phase = EngineeringPhase.REVIEW
        self._status(f"Phase: REVIEW")
        state.review_findings.append("Verification passed")
        self._status("Reviewing changes...")
        self._review_changes(state)

        state.phase = EngineeringPhase.FINALIZE
        self._status(f"Phase: FINALIZE")
        state.final_status = "COMPLETED"
        self._status("Task completed successfully")

        return self._engineering_result(base_result)

    def _review_changes(self, state: EngineeringTaskState) -> None:
        try:
            diff_result = self._execute_tool_call({
                "tool": "git_diff",
                "arguments": {"project_path": str(self.project_path)},
            })
            if diff_result.success and diff_result.output:
                state.review_findings.append(f"Git diff inspected: {diff_result.output[:200]}")
            else:
                state.review_findings.append("No git diff available or not a git repository")
        except Exception:
            state.review_findings.append("Review skipped: unable to inspect git diff")

    def _run_verification_command(self, command: str, state: EngineeringTaskState) -> tuple:
        try:
            tool_result = self._execute_tool_call({
                "tool": "bash",
                "arguments": {"command": command, "cwd": str(self.project_path)},
            })
            success = tool_result.success
            output = (tool_result.output or tool_result.error or "").strip()
            summary = output[:500] if output else ("passed" if success else "failed")
            return success, summary
        except Exception as e:
            return False, f"Verification error: {str(e)}"

    def _build_repair_context(self, state: EngineeringTaskState, verification_failure: Dict[str, Any]) -> Dict[str, Any]:
        failure_command = verification_failure.get("command", "")
        failure_summary = verification_failure.get("summary", "")
        recent_observations = [
            f"Verification failed for command: {failure_command}",
            f"Failure output: {failure_summary[:500]}",
        ]
        if state.modified_files:
            recent_observations.append(f"Modified files: {', '.join(state.modified_files)}")

        return {
            "user_request": state.goal,
            "project_context": self._project_context.to_dict(),
            "project_profile": self._project_context,
            "conversation": self._conversation.to_list(),
            "available_tools": self._tool_registry.list_tools(),
            "recent_tool_results": [],
            "recent_observations": recent_observations,
            "current_step": "repair",
            "active_skills": [s.to_dict() for s in getattr(self, "_active_skills", [])],
            "skill_instructions": "",
            "memory_context": self.memory.retrieve_relevant(state.goal),
            "instructions": [
                "You are Argus, an autonomous coding agent in REPAIR mode.",
                "A verification command failed. Analyze the failure and fix the code.",
                f"Failed command: {failure_command}",
                f"Failure details: {failure_summary[:500]}",
                "Use the available tools to inspect the code, identify the issue, and apply a fix.",
                "After making changes, verify the fix if possible.",
            ],
        }

    def _run_model_repair(self, state: EngineeringTaskState, verification_failure: Dict[str, Any]) -> str:
        if not self._model:
            return "No model available for autonomous repair"

        context = self._build_repair_context(state, verification_failure)
        try:
            response = self._model_reason(context, state.goal)
            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                return response.get("response", "Model returned no repair actions")

            results = []
            for tc in tool_calls:
                tool_result = self._execute_tool_call(tc)
                results.append(tool_result)
                state.modified_files.extend(extract_modified_files([tool_result]))

            successes = [r for r in results if r.success]
            failures = [r for r in results if not r.success]
            summary = f"Model repair executed {len(results)} tool call(s): {len(successes)} succeeded, {len(failures)} failed"
            if failures:
                errors = [r.error for r in failures[:3] if r.error]
                if errors:
                    summary += f". Errors: {'; '.join(errors)}"
            return summary
        except Exception as e:
            return f"Model repair failed: {str(e)}"

    def _should_replan(self, state: EngineeringTaskState, trigger_phase: str = "VERIFY") -> bool:
        if not state:
            return False
        if not self._model:
            return False
        if state.plan_revision_count >= getattr(self.config, "max_plan_revisions", 2):
            return False
        if not state.plan_steps:
            return False

        if trigger_phase == "VERIFY" and state.verification_results:
            last_verification = state.verification_results[-1]
            if not last_verification.get("success", True):
                return True

        contradiction = self._check_execution_contradictions(state)
        if contradiction and contradiction.get("replan", False):
            return True

        if trigger_phase == "EXECUTE":
            execution_evidence = [e for e in state.evidence if e.phase == EngineeringPhase.EXECUTE.value]
            if execution_evidence:
                model_result = self._model_evaluate_contradiction(state)
                if model_result.get("replan", False):
                    return True

        return False

    def _build_replan_context(self, state: EngineeringTaskState) -> Dict[str, Any]:
        last_verification = state.verification_results[-1] if state.verification_results else {}
        execution_evidence = [e.to_dict() for e in state.evidence if e.phase == EngineeringPhase.EXECUTE.value][-5:]
        recent_observations = []

        if last_verification:
            recent_observations.append(
                f"Verification failed for command: {last_verification.get('command', '')}"
            )
            recent_observations.append(
                f"Failure output: {last_verification.get('summary', '')[:500]}"
            )
        elif execution_evidence:
            recent_observations.append("Execution evidence indicating contradiction:")
            for ev in execution_evidence:
                recent_observations.append(f"  - {ev.get('category', '')}: {ev.get('output_summary', '')[:200]}")

        if state.investigation_findings:
            for finding in state.investigation_findings[-3:]:
                recent_observations.append(
                    f"Investigation: {finding.source} {finding.action}: {finding.result_summary[:200]}"
                )
        if state.modified_files:
            recent_observations.append(f"Modified files: {', '.join(state.modified_files)}")

        plan_with_assumptions = []
        for i, step in enumerate(state.plan_steps):
            plan_with_assumptions.append({
                "step_index": i,
                "action": step.get("action", ""),
                "description": step.get("description", ""),
                "status": step.get("status", "pending"),
                "assumptions": step.get("assumptions", []),
            })

        return {
            "user_request": state.goal,
            "project_context": self._project_context.to_dict(),
            "project_profile": self._project_context,
            "conversation": self._conversation.to_list(),
            "available_tools": self._tool_registry.list_tools(),
            "recent_tool_results": [],
            "recent_observations": recent_observations,
            "current_step": "replan",
            "active_skills": [s.to_dict() for s in getattr(self, "_active_skills", [])],
            "skill_instructions": "",
            "memory_context": self.memory.retrieve_relevant(state.goal),
            "instructions": [
                "You are Argus, an autonomous coding agent in REPLAN mode.",
                "The current plan is invalid due to a verification failure or execution contradiction. You must revise the plan.",
                f"Original request: {state.goal}",
                f"Current plan: {plan_with_assumptions}",
                f"Completed steps: {state.completed_steps}",
                f"New evidence: {last_verification.get('summary', '')[:500] if last_verification else 'Execution contradiction'}",
                "Return a revised plan as JSON in this format:",
                '{"plan": [{"action": "step_name", "description": "what to do", "assumptions": ["optional assumption"]}]}',
                "The revised plan should address the contradiction while preserving completed work.",
            ],
        }

    def _run_model_replan(self, state: EngineeringTaskState) -> str:
        if not self._model:
            return "No model available for replanning"

        context = self._build_replan_context(state)
        try:
            response = self._model_reason(context, state.goal)
            text = response.get("response", "")
            revised_plan = self._parse_revised_plan(text)
            if revised_plan:
                state.record_revised_plan(revised_plan)
                return f"Plan revised (revision {state.plan_revision_count})"
            return f"Model returned no revised plan: {text[:200]}"
        except Exception as e:
            return f"Replanning failed: {str(e)}"

    def _is_significant_tool_result(self, tool_result: Any) -> bool:
        if isinstance(tool_result, dict):
            success = tool_result.get("success", False)
            tool_name = tool_result.get("tool", "")
            output = tool_result.get("output", "") or tool_result.get("error", "") or ""
        else:
            success = getattr(tool_result, "success", False)
            tool_name = getattr(tool_result, "tool", "")
            output = getattr(tool_result, "output", "") or getattr(tool_result, "error", "") or ""

        if not success:
            return True

        output_lower = output.lower()
        significant_patterns = [
            "not found", "missing", "unexpected", "error:", "failed",
            "no such file", "does not exist", "undefined", "none",
            "conflict", "contradicts", "differs from",
        ]
        for pattern in significant_patterns:
            if pattern in output_lower:
                return True

        if tool_name in ("git_status", "git_diff", "git_log"):
            return True

        return False

    def _categorize_tool_result(self, tool_result: Any) -> str:
        if isinstance(tool_result, dict):
            tool_name = tool_result.get("tool", "")
            output = tool_result.get("output", "") or tool_result.get("error", "") or ""
        else:
            tool_name = getattr(tool_result, "tool", "")
            output = getattr(tool_result, "output", "") or getattr(tool_result, "error", "") or ""

        output_lower = output.lower()
        if tool_name in ("read_file", "write_file", "edit_file"):
            if "not found" in output_lower or "no such file" in output_lower or "does not exist" in output_lower:
                return EvidenceCategory.MISSING_EXPECTED.value
            return EvidenceCategory.FILE_DISCOVERY.value
        if tool_name == "grep":
            if "not found" in output_lower or "no matches" in output_lower:
                return EvidenceCategory.MISSING_EXPECTED.value
            return EvidenceCategory.SYMBOL_LOCATION.value
        if tool_name in ("git_status", "git_diff", "git_log"):
            return EvidenceCategory.GIT_STATE.value
        if "test" in tool_name or "pytest" in output_lower or "test" in output_lower:
            return EvidenceCategory.TEST_RESULT.value
        if "build" in tool_name or "compile" in output_lower or "build" in output_lower:
            return EvidenceCategory.BUILD_RESULT.value
        if "bash" in tool_name or "command" in tool_name:
            return EvidenceCategory.COMMAND_RESULT.value
        return EvidenceCategory.TOOL_OUTPUT.value

    def _extract_execution_evidence(self, state: EngineeringTaskState, tool_results: List[Any]) -> None:
        for tr in tool_results:
            if not self._is_significant_tool_result(tr):
                continue

            if isinstance(tr, dict):
                tool_name = tr.get("tool", "")
                success = tr.get("success", False)
                output = tr.get("output", "") or tr.get("error", "") or ""
            else:
                tool_name = getattr(tr, "tool", "")
                success = getattr(tr, "success", False)
                output = getattr(tr, "output", "") or getattr(tr, "error", "") or ""

            category = self._categorize_tool_result(tr)
            summary = output[:300] if output else ("succeeded" if success else "failed")
            state.add_evidence(
                EngineeringPhase.EXECUTE.value,
                command=tool_name,
                success=success,
                output_summary=summary,
                category=category,
            )

    def _check_execution_contradictions(self, state: EngineeringTaskState) -> Optional[Dict[str, Any]]:
        if not state.plan_steps:
            return None

        for evidence in state.evidence:
            if evidence.phase != EngineeringPhase.EXECUTE.value:
                continue

            contradiction = self._deterministic_contradiction_check(state, evidence)
            if contradiction:
                return contradiction

        return None

    def _deterministic_contradiction_check(self, state: EngineeringTaskState, evidence: Any) -> Optional[Dict[str, Any]]:
        output_lower = (evidence.output_summary or "").lower()
        category = evidence.category or ""

        if category == EvidenceCategory.MISSING_EXPECTED.value:
            return {
                "replan": True,
                "reason": f"Expected resource missing: {evidence.output_summary[:200]}",
                "affected_steps": [i for i, step in enumerate(state.plan_steps) if step.get("status") != "completed"],
                "evidence_category": category,
            }

        if "not found" in output_lower or "does not exist" in output_lower or "no such file" in output_lower:
            return {
                "replan": True,
                "reason": f"Resource not found during execution: {evidence.output_summary[:200]}",
                "affected_steps": [i for i, step in enumerate(state.plan_steps) if step.get("status") != "completed"],
                "evidence_category": category,
            }

        if "conflict" in output_lower or "contradicts" in output_lower:
            return {
                "replan": True,
                "reason": f"Tool output indicates conflict: {evidence.output_summary[:200]}",
                "affected_steps": [i for i, step in enumerate(state.plan_steps) if step.get("status") != "completed"],
                "evidence_category": category,
            }

        for step in state.plan_steps:
            if step.get("status") == "completed":
                continue
            assumptions = step.get("assumptions", [])
            if not assumptions:
                continue
            for assumption in assumptions:
                assumption_lower = assumption.lower()
                if any(word in output_lower for word in assumption_lower.split()):
                    if "not " in output_lower or "missing" in output_lower or "unexpected" in output_lower:
                        return {
                            "replan": True,
                            "reason": f"Plan assumption invalidated: '{assumption}' contradicted by tool output",
                            "affected_steps": [i for i, s in enumerate(state.plan_steps) if s.get("status") != "completed"],
                            "evidence_category": EvidenceCategory.IMPLEMENTATION_DIFFERS.value,
                            "invalidated_assumption": assumption,
                        }

        return None

    def _model_evaluate_contradiction(self, state: EngineeringTaskState) -> Dict[str, Any]:
        recent_evidence = [e.to_dict() for e in state.evidence[-5:]]
        plan_with_assumptions = []
        for i, step in enumerate(state.plan_steps):
            plan_with_assumptions.append({
                "step_index": i,
                "action": step.get("action", ""),
                "description": step.get("description", ""),
                "status": step.get("status", "pending"),
                "assumptions": step.get("assumptions", []),
            })

        context = {
            "user_request": state.goal,
            "project_context": self._project_context.to_dict(),
            "current_plan": plan_with_assumptions,
            "completed_steps": state.completed_steps,
            "recent_evidence": recent_evidence,
            "current_step": "evaluate_contradiction",
        }

        instructions = [
            "You are Argus evaluating whether new execution evidence invalidates the current plan.",
            "Return a JSON object with this exact format:",
            '{"replan": true or false, "reason": "concise explanation", "affected_steps": [0, 1, ...]}',
            "Do not expose chain-of-thought. Only return the JSON decision.",
            f"Goal: {state.goal}",
            f"Plan: {plan_with_assumptions}",
            f"Recent evidence: {recent_evidence}",
        ]

        context["instructions"] = instructions
        context["recent_observations"] = [str(e) for e in recent_evidence]

        try:
            response = self._model_reason(context, state.goal)
            text = response.get("response", "")
            import json
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if isinstance(data, dict) and "replan" in data:
                        return {
                            "replan": bool(data.get("replan", False)),
                            "reason": data.get("reason", ""),
                            "affected_steps": data.get("affected_steps", []),
                        }
                except Exception:
                    pass
        except Exception:
            pass

        return {"replan": False, "reason": "Model evaluation inconclusive", "affected_steps": []}

    def _execute_revised_plan(self, state: EngineeringTaskState) -> str:
        if not self._model:
            return "No model available for revised plan execution"

        revised_plan = state.plan_steps
        if not revised_plan:
            return "No revised plan to execute"

        results_summary = []
        for step_index, step in enumerate(revised_plan):
            if self._cancelled:
                return "Revised plan execution cancelled"

            if step.get("status") == "completed":
                continue

            step_action = step.get("action", "")
            step_description = step.get("description", "")
            self._status(f"Executing revised step {step_index + 1}/{len(revised_plan)}: {step_action}")

            context = {
                "user_request": state.goal,
                "project_context": self._project_context.to_dict(),
                "project_profile": self._project_context,
                "conversation": self._conversation.to_list(),
                "available_tools": self._tool_registry.list_tools(),
                "recent_tool_results": [],
                "recent_observations": [
                    f"Revised plan step: {step_action}",
                    f"Description: {step_description}",
                    f"Completed steps: {state.completed_steps}",
                ],
                "current_step": "execute_revised_plan",
                "active_skills": [s.to_dict() for s in getattr(self, "_active_skills", [])],
                "skill_instructions": "",
                "memory_context": self.memory.retrieve_relevant(state.goal),
                "instructions": [
                    "You are Argus executing a revised plan step.",
                    f"Goal: {state.goal}",
                    f"Current step: {step_action} - {step_description}",
                    f"Completed steps: {state.completed_steps}",
                    "Use the available tools to complete this step.",
                    "After completing the step, verify if the work is done.",
                ],
            }

            try:
                response = self._model_reason(context, state.goal)
                tool_calls = response.get("tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        if self._cancelled:
                            break
                        tool_result = self._execute_tool_call(tc)
                        results_summary.append(tool_result)
                        state.modified_files.extend(extract_modified_files([tool_result]))

                step["status"] = "completed"

            except Exception as e:
                return f"Revised plan execution failed: {str(e)}"

        summary_parts = [f"Executed {len(results_summary)} tool call(s)"]
        successes = [r for r in results_summary if (r.success if isinstance(r, dict) else getattr(r, "success", False))]
        summary_parts.append(f"{len(successes)} succeeded")
        return ", ".join(summary_parts)

    def _parse_revised_plan(self, text: str) -> List[Dict[str, Any]]:
        import json
        import re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                plan = data.get("plan", [])
                if isinstance(plan, list):
                    return [step for step in plan if isinstance(step, dict) and "action" in step]
            except Exception:
                pass
        return []

    def _build_investigation_context(self, request: str) -> Dict[str, Any]:
        recent_observations = []
        if self._engineering_state and self._engineering_state.investigation_findings:
            for finding in self._engineering_state.investigation_findings[-3:]:
                recent_observations.append(
                    f"Investigation: {finding.source} {finding.action}: {finding.result_summary[:200]}"
                )

        return {
            "user_request": request,
            "project_context": self._project_context.to_dict(),
            "project_profile": self._project_context,
            "conversation": self._conversation.to_list(),
            "available_tools": self._tool_registry.list_tools(),
            "recent_tool_results": [],
            "recent_observations": recent_observations,
            "current_step": "investigate",
            "active_skills": [s.to_dict() for s in getattr(self, "_active_skills", [])],
            "skill_instructions": "",
            "memory_context": self.memory.retrieve_relevant(request),
            "instructions": [
                "You are Argus, an autonomous coding agent in INVESTIGATE mode.",
                "Your goal is to gather evidence about the codebase before planning.",
                "Use the available tools to inspect relevant files, search for symbols, check git status, and retrieve project memory.",
                "Focus on finding the most relevant information for the task.",
                "Return your findings as a concise summary.",
            ],
        }
        last_verification = state.verification_results[-1] if state.verification_results else {}
        execution_evidence = [e.to_dict() for e in state.evidence if e.phase == EngineeringPhase.EXECUTE.value][-5:]
        recent_observations = []

        if last_verification:
            recent_observations.append(
                f"Verification failed for command: {last_verification.get('command', '')}"
            )
            recent_observations.append(
                f"Failure output: {last_verification.get('summary', '')[:500]}"
            )

        if execution_evidence:
            recent_observations.append("Execution evidence:")
            for ev in execution_evidence:
                recent_observations.append(f"  - {ev.get('category', '')}: {ev.get('output_summary', '')[:200]}")

        if state.investigation_findings:
            for finding in state.investigation_findings[-3:]:
                recent_observations.append(
                    f"Investigation: {finding.source} {finding.action}: {finding.result_summary[:200]}"
                )
        if state.modified_files:
            recent_observations.append(f"Modified files: {', '.join(state.modified_files)}")

        return {
            "user_request": state.goal,
            "project_context": self._project_context.to_dict(),
            "project_profile": self._project_context,
            "conversation": self._conversation.to_list(),
            "available_tools": self._tool_registry.list_tools(),
            "recent_tool_results": [],
            "recent_observations": recent_observations,
            "current_step": "replan",
            "active_skills": [s.to_dict() for s in getattr(self, "_active_skills", [])],
            "skill_instructions": "",
            "memory_context": self.memory.retrieve_relevant(state.goal),
            "instructions": [
                "You are Argus, an autonomous coding agent in REPLAN mode.",
                "The current plan is invalid due to a verification failure or execution contradiction. You must revise the plan.",
                f"Original request: {state.goal}",
                f"Current plan: {state.plan_steps}",
                f"Completed steps: {state.completed_steps}",
                f"New evidence: {last_verification.get('summary', '')[:500] if last_verification else 'Execution contradiction'}",
                "Return a revised plan as JSON in this format:",
                '{"plan": [{"action": "step_name", "description": "what to do", "assumptions": ["optional assumption"]}]}',
                "The revised plan should address the contradiction while preserving completed work.",
            ],
        }
        recent_observations = []
        if self._engineering_state and self._engineering_state.investigation_findings:
            for finding in self._engineering_state.investigation_findings[-3:]:
                recent_observations.append(
                    f"Investigation: {finding.source} {finding.action}: {finding.result_summary[:200]}"
                )

        return {
            "user_request": request,
            "project_context": self._project_context.to_dict(),
            "project_profile": self._project_context,
            "conversation": self._conversation.to_list(),
            "available_tools": self._tool_registry.list_tools(),
            "recent_tool_results": [],
            "recent_observations": recent_observations,
            "current_step": "investigate",
            "active_skills": [s.to_dict() for s in getattr(self, "_active_skills", [])],
            "skill_instructions": "",
            "memory_context": self.memory.retrieve_relevant(request),
            "instructions": [
                "You are Argus, an autonomous coding agent in INVESTIGATE mode.",
                "Your goal is to gather evidence about the codebase before planning.",
                "Use the available tools to inspect relevant files, search for symbols, check git status, and retrieve project memory.",
                "Focus on finding the most relevant information for the task.",
                "Return your findings as a concise summary.",
            ],
        }

    def _run_investigation(self, request: str) -> None:
        if not self._model:
            return

        context = self._build_investigation_context(request)
        try:
            response = self._model_reason(context, request)
            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                if self._engineering_state:
                    self._engineering_state.add_investigation(
                        source="model",
                        action="reason",
                        result_summary=response.get("response", "No investigation actions returned"),
                    )
                return

            for tc in tool_calls:
                if self._cancelled:
                    break
                tool_result = self._execute_tool_call(tc)
                if self._engineering_state:
                    relevant_files = []
                    if tool_result.success and tool_result.tool in ("read_file", "grep", "glob"):
                        output = tool_result.output or ""
                        for line in output.splitlines()[:10]:
                            if ":" in line:
                                relevant_files.append(line.split(":")[0].strip())
                            elif line.strip().endswith(".py") or line.strip().endswith(".js"):
                                relevant_files.append(line.strip())

                    self._engineering_state.add_investigation(
                        source=tool_result.tool,
                        action=str(tc.get("arguments", {}))[:200],
                        result_summary=(tool_result.output or tool_result.error or "")[:300],
                        relevant_files=relevant_files,
                    )
        except Exception:
            pass

    def _engineering_result(self, base_result: Dict[str, Any]) -> Dict[str, Any]:
        if self._engineering_state:
            base_result["engineering"] = self._engineering_state.to_dict()
            base_result["final_status"] = self._engineering_state.final_status
            if self._engineering_state.final_status == "COMPLETED":
                base_result["status"] = "COMPLETED"
                base_result["success"] = True
            elif self._engineering_state.final_status == "FAILED":
                base_result["status"] = "FAILED"
                base_result["success"] = False
                base_result["failure_reason"] = "verification_failed_after_repair"
        return base_result

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
