import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AgentCoreConfig, ConfigLoader, resolve_skill_paths
from .context import ProjectContext
from .events import EventBus, EventType, create_event
from .memory import MemoryManager
from .persistence import TaskPersistenceManager
from .planner import Planner
from .router import RoutingResult, SkillRouter
from .runtimes.base import FinishReason, RuntimeAdapter, RuntimeResponse, ToolResult
from .skills import Skill, SkillRegistry
from .task import InvalidStateTransitionError, PlanStep, StepStatus, Task, TaskState
from .tools import ToolManager
from .verifier import Verifier

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    model: str | None = None
    provider: str | None = None
    max_iterations: int = 10
    max_tool_calls: int = 50
    max_runtime_seconds: int = 300
    timeout: int = 300
    tool_timeout: int | None = None
    enable_verification: bool = True
    run_format_check: bool = True
    run_build_check: bool = True
    run_tests: bool = True
    verification_scope: str = "project"
    max_replans: int = 3


@dataclass
class ProjectContextData:
    """Structured facts discovered from the repository."""

    project_root: str = ""
    language: str | None = None
    framework: str | None = None
    build_system: str | None = None
    package_manager: str | None = None
    git_status: dict[str, Any] = field(default_factory=dict)
    git_diff: str = ""
    config_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    readme: str | None = None
    documentation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "language": self.language,
            "framework": self.framework,
            "build_system": self.build_system,
            "package_manager": self.package_manager,
            "git": {
                "status": self.git_status,
                "diff": self.git_diff[:5000],
            },
            "config_files": self.config_files[:20],
            "test_files": self.test_files[:20],
            "readme": self.readme,
            "documentation": self.documentation[:20],
        }


@dataclass
class TaskContextData:
    """Information specific to the current task."""

    user_request: str = ""
    task_id: str = ""
    current_state: str = ""
    plan: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    memory_context: dict[str, Any] = field(default_factory=dict)
    selected_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "current_state": self.current_state,
            "user_request": self.user_request,
            "plan": self.plan,
            "hypotheses": self.hypotheses,
            "observations": self.observations,
            "tool_results": self.tool_results,
            "memory_context": self.memory_context,
            "selected_skills": self.selected_skills,
        }


@dataclass
class MemoryContextData:
    """Relevant historical information recalled from MemoryBackend."""

    results: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "results": self.results[:10],
        }


@dataclass
class SkillContextData:
    """Context about loaded/routed skills."""

    selected: list[str] = field(default_factory=list)
    available: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected,
            "available": self.available,
            "attributes": self.attributes,
        }


@dataclass
class RuntimeContextData:
    """Context about the runtime/provider."""

    runtime_name: str = ""
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime": self.runtime_name,
            "model": self.model,
        }


class ContextBuilder:
    """
    Combines project, task, memory, skill, and runtime context into a
    model-facing context dictionary.
    """

    MAX_TOOL_RESULTS = 10
    MAX_MEMORY_RECORDS = 10
    MAX_PLAN_STEPS = 20
    MAX_HYPOTHESES = 10

    @staticmethod
    def build(
        task: Task, skills: list[Skill], memory_results: list[dict], tool_results: list[dict]
    ) -> dict[str, Any]:
        project_data = ProjectContextData(
            project_root=task.project,
            language=task.project_context.get("language"),
            framework=task.project_context.get("framework"),
            build_system=task.project_context.get("build_system"),
            package_manager=task.project_context.get("package_manager"),
            git_status=task.project_context.get("git_status", {}),
            git_diff=task.project_context.get("git_diff", ""),
            config_files=task.project_context.get("config_files", []),
            test_files=task.project_context.get("test_files", []),
            readme=task.project_context.get("readme"),
            documentation=task.project_context.get("documentation", []),
        )

        memory_context = MemoryContextData(
            results=memory_results[: ContextBuilder.MAX_MEMORY_RECORDS],
            count=len(memory_results),
        )

        skill_context = SkillContextData(
            selected=task.selected_skills,
            available=[s.name for s in skills],
            attributes=task.attributes,
        )

        runtime_context = RuntimeContextData(
            runtime_name="agent",
            model=task.attributes.get("model"),
        )

        task_data = TaskContextData(
            user_request=task.user_request,
            task_id=task.task_id,
            current_state=task.current_state.value
            if hasattr(task.current_state, "value")
            else str(task.current_state),
            plan=task.plan[: ContextBuilder.MAX_PLAN_STEPS],
            hypotheses=task.hypotheses[: ContextBuilder.MAX_HYPOTHESES],
            tool_results=tool_results[: ContextBuilder.MAX_TOOL_RESULTS],
            memory_context=memory_context.to_dict(),
        )

        return {
            "project_context": project_data.to_dict(),
            "task_context": task_data.to_dict(),
            "memory_context": memory_context.to_dict(),
            "skill_context": skill_context.to_dict(),
            "runtime_context": runtime_context.to_dict(),
            "instructions": [
                "You are an AI coding agent. Work iteratively.",
                "Analyze the task, propose actions, and observe results.",
                "Use tools to explore and modify code.",
                "Only output final answers when truly complete.",
                "For code changes, always verify with tests.",
            ],
            "user_request": task.user_request,
        }


class Agent:
    def __init__(
        self,
        runtime: RuntimeAdapter,
        memory: MemoryManager,
        config: AgentConfig | None = None,
        project_path: str | Path | None = None,
        agentcore_config: AgentCoreConfig | None = None,
        event_bus: EventBus | None = None,
        persistence: TaskPersistenceManager | None = None,
    ):
        self.runtime = runtime
        self.memory = memory
        self.config = config or AgentConfig()
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self._agentcore_config = agentcore_config or ConfigLoader.discover(self.project_path)
        self._event_bus = event_bus or EventBus()
        self._persistence = persistence

        self._tool_manager = ToolManager(self.project_path, tool_timeout=self.config.tool_timeout)
        self._verifier = Verifier(self.project_path)
        self._planner = Planner()

        if hasattr(self.memory, "set_event_bus"):
            self.memory.set_event_bus(self._event_bus)

        if self._persistence is not None and hasattr(self._persistence, "set_event_bus"):
            self._persistence.set_event_bus(self._event_bus)

        self._current_task: Task | None = None
        self._iterations = 0
        self._tools_used = 0
        self._tool_results: list[dict[str, Any]] = []
        self._start_time = 0
        self._cancelled = False
        self._replan_count = 0
        self._baseline_changed_files: list[str] | None = None

    def _emit(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._event_bus.subscriber_count > 0:
            event = create_event(
                event_type=event_type,
                task_id=self._current_task.task_id if self._current_task else "",
                iteration=self._iterations,
                data=data or {},
                metadata=metadata or {},
            )
            self._event_bus.emit(event)

    def _emit_state_changed(
        self,
        previous_state: TaskState,
        new_state: TaskState,
        reason: str = "",
        step_id: str | None = None,
    ) -> None:
        self._emit(
            EventType.TASK_STATE_CHANGED,
            data={
                "previous_state": previous_state.value,
                "new_state": new_state.value,
                "reason": reason,
                "step_id": step_id,
                "iteration": self._iterations,
            },
        )

    def _checkpoint(self) -> None:
        if self._persistence is not None and self._current_task is not None:
            try:
                self._persistence.checkpoint(self._current_task)
            except Exception as e:
                logger.debug(f"Checkpoint failed: {e}")

    def cancel(self) -> None:
        if self._current_task is None:
            return
        self._cancelled = True
        try:
            previous = self._current_task.current_state
            self._current_task.transition(TaskState.CANCELLED, reason="cancelled_by_user")
            self._emit_state_changed(previous, TaskState.CANCELLED, reason="cancelled_by_user")
            self._emit(EventType.TASK_CANCELLED, data={"task_id": self._current_task.task_id})
        except InvalidStateTransitionError:
            pass
        try:
            self.runtime.cancel()
        except Exception:
            pass
        try:
            self._tool_manager.cancel_in_flight()
        except Exception:
            pass

    def execute(self, user_request: str, project: str | None = None) -> dict[str, Any]:
        self._start_time = time.time()
        self._cancelled = False
        self._replan_count = 0

        self._current_task = Task(
            user_request=user_request,
            project=project or str(self.project_path),
        )
        self._current_task.transition(TaskState.ANALYZING)
        self._emit_state_changed(TaskState.CREATED, TaskState.ANALYZING, reason="task_started")
        self._checkpoint()
        logger.info(f"Task created: {self._current_task.task_id}")
        self._emit(
            EventType.TASK_STARTED,
            data={"user_request": user_request, "project": project or str(self.project_path)},
        )

        project_context = self._load_project_context()
        self._current_task.project_context = project_context

        memory_results = self._load_memory_context()
        self._current_task.memory_context = {
            "results": memory_results,
            "count": len(memory_results),
        }

        self._baseline_changed_files = self._capture_changed_files()

        try:
            self._current_task.transition(TaskState.ROUTING)
            self._emit_state_changed(
                TaskState.ANALYZING, TaskState.ROUTING, reason="routing_skills"
            )
        except InvalidStateTransitionError:
            pass
        routing = self._route_skills(user_request, project_context)
        self._current_task.selected_skills = routing.selected_skills
        self._current_task.attributes = routing.attributes

        try:
            self._current_task.transition(TaskState.INVESTIGATING)
            self._emit_state_changed(
                TaskState.ROUTING, TaskState.INVESTIGATING, reason="investigating"
            )
        except InvalidStateTransitionError:
            pass
        investigation = self._investigate(user_request)
        self._current_task.hypotheses.append(investigation)

        try:
            self._current_task.transition(TaskState.PLANNING)
            self._emit_state_changed(
                TaskState.INVESTIGATING, TaskState.PLANNING, reason="creating_plan"
            )
        except InvalidStateTransitionError:
            pass
        plan = self._generate_plan(user_request, project_context)
        self._current_task.plan = [s.to_dict() for s in plan]
        self._checkpoint()

        try:
            self._current_task.transition(TaskState.RUNNING)
            self._emit_state_changed(
                TaskState.PLANNING, TaskState.RUNNING, reason="starting_execution"
            )
        except InvalidStateTransitionError:
            pass
        results = self._run_iterative_loop(plan)

        verification = None
        if self._cancelled:
            final_state = TaskState.CANCELLED
        else:
            try:
                self._current_task.transition(TaskState.VERIFYING)
                self._emit_state_changed(
                    TaskState.RUNNING, TaskState.VERIFYING, reason="verification_phase"
                )
            except InvalidStateTransitionError:
                pass
            verification = self._run_verification(results)

            if verification["overall_passed"]:
                final_state = TaskState.COMPLETED
                try:
                    self._current_task.transition(TaskState.COMPLETED)
                    self._emit_state_changed(
                        TaskState.VERIFYING, TaskState.COMPLETED, reason="verification_passed"
                    )
                except InvalidStateTransitionError:
                    pass
                self._checkpoint()
                self._emit(
                    EventType.TASK_COMPLETED,
                    data={
                        "success": True,
                        "iterations": self._iterations,
                        "tools_used": self._tools_used,
                    },
                )
            else:
                final_state = self._handle_verification_failure(verification)

        if final_state in (TaskState.FAILED, TaskState.CANCELLED):
            self._emit(
                EventType.TASK_FAILED
                if final_state == TaskState.FAILED
                else EventType.TASK_CANCELLED,
                data={
                    "success": False,
                    "iterations": self._iterations,
                    "tools_used": self._tools_used,
                    "final_state": final_state.value,
                },
            )

        self._store_task_memory(final_state == TaskState.COMPLETED)
        self._checkpoint()
        logger.info(f"Task completed with state: {final_state.value}")

        return {
            "task": self._current_task.to_dict(),
            "verification": verification
            if verification is not None
            else {"overall_passed": final_state == TaskState.COMPLETED},
            "success": final_state == TaskState.COMPLETED,
            "tools_used": self._tools_used,
            "iterations": self._iterations,
            "stopped_reason": results.get("stopped_reason"),
        }

    def _handle_verification_failure(self, verification: dict[str, Any]) -> TaskState:
        if self._cancelled:
            return TaskState.CANCELLED
        if self._replan_count >= self.config.max_replans:
            try:
                self._current_task.transition(TaskState.FAILED, reason="max_replans_reached")
                self._emit_state_changed(
                    TaskState.VERIFYING, TaskState.FAILED, reason="max_replans_reached"
                )
            except InvalidStateTransitionError:
                pass
            return TaskState.FAILED

        try:
            self._current_task.transition(TaskState.REPLANNING)
            self._emit_state_changed(
                TaskState.VERIFYING, TaskState.REPLANNING, reason="verification_failed"
            )
        except InvalidStateTransitionError:
            pass

        new_plan = self._replan(verification_failures=verification.get("failures", []))
        if new_plan is None:
            try:
                self._current_task.transition(TaskState.FAILED, reason="replan_failed")
                self._emit_state_changed(
                    TaskState.REPLANNING, TaskState.FAILED, reason="replan_failed"
                )
            except InvalidStateTransitionError:
                pass
            return TaskState.FAILED

        self._replan_count += 1
        self._current_task.plan = [s.to_dict() for s in new_plan]
        try:
            self._current_task.transition(TaskState.RUNNING)
            self._emit_state_changed(
                TaskState.REPLANNING, TaskState.RUNNING, reason="replan_executing"
            )
        except InvalidStateTransitionError:
            pass
        self._run_iterative_loop(new_plan)
        verification = self._run_verification(self._tool_results)
        if verification["overall_passed"]:
            try:
                self._current_task.transition(TaskState.COMPLETED)
                self._emit_state_changed(
                    TaskState.RUNNING,
                    TaskState.COMPLETED,
                    reason="verification_passed_after_replan",
                )
            except InvalidStateTransitionError:
                pass
            self._emit(
                EventType.TASK_COMPLETED,
                data={
                    "success": True,
                    "replanned": True,
                    "iterations": self._iterations,
                    "tools_used": self._tools_used,
                },
            )
            return TaskState.COMPLETED
        return self._handle_verification_failure(verification)

    def _load_project_context(self) -> dict[str, Any]:
        ctx = ProjectContext(self.project_path)
        return ctx.discover()

    def _load_memory_context(self) -> list[dict]:
        if not self._current_task:
            return []
        query_parts = []
        query_parts.extend(self._current_task.user_request.split()[:5])
        lang = self._current_task.project_context.get("language", "")
        if lang:
            query_parts.append(lang)
        query_parts.extend(self._current_task.selected_skills)
        query = " ".join(query_parts)
        task_id = self._current_task.task_id if self._current_task else ""
        try:
            results = self.memory.search(
                query, self._current_task.project, limit=10, task_id=task_id
            )
            return results
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
            return []

    def _capture_changed_files(self) -> list[str] | None:
        if not (self.project_path / ".git").exists():
            return []
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return [f for f in result.stdout.strip().split("\n") if f]
        except Exception as e:
            logger.debug(f"Failed to capture changed files: {e}")
            return None

    def _route_skills(self, prompt: str, context: dict[str, Any]) -> RoutingResult:
        skill_paths = resolve_skill_paths(self._agentcore_config)
        registry = SkillRegistry(skill_paths)
        skills = registry.discover(skill_paths)
        self._skill_registry = registry
        self._available_skills = skills
        for skill in skills:
            self._emit(EventType.SKILL_DISCOVERED, data={"name": skill.name})
        router = SkillRouter(skills)
        result = router.route(prompt, context)
        for skill_name in result.selected_skills:
            self._emit(EventType.SKILL_SELECTED, data={"name": skill_name})
        loaded_skills = []
        for skill_name in result.selected_skills:
            skill = registry.find(skill_name)
            if skill:
                loaded_skills.append(skill)
                self._emit(EventType.SKILL_LOADED, data={"name": skill_name, "path": skill.path})
        result.loaded_skills = loaded_skills
        self._emit(
            EventType.ROUTE_SELECTED,
            data={
                "selected_skills": result.selected_skills,
                "attributes": result.attributes,
            },
        )
        return result

    def _investigate(self, prompt: str) -> dict[str, Any]:
        return {
            "statement": f"Investigate: {prompt}",
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "status": "PROPOSED",
        }

    def _generate_plan(self, request: str, context: dict) -> list[PlanStep]:
        request_lower = request.lower()
        if any(word in request_lower for word in ["fix", "crash", "bug", "error", "fail"]):
            plan = self._planner.plan("bug_fix", request, context)
        elif any(word in request_lower for word in ["implement", "add", "create", "new"]):
            plan = self._planner.plan("feature_implement", request, context)
        elif any(word in request_lower for word in ["refactor", "simplify", "clean"]):
            plan = self._planner.plan("refactor", request, context)
        elif any(word in request_lower for word in ["investigate", "explain", "why", "what"]):
            plan = [
                PlanStep(
                    action="investigate",
                    description="Explore the codebase to understand the request",
                ),
                PlanStep(action="summarize", description="Summarize findings for the user"),
            ]
        else:
            plan = self._planner.plan("investigate", request, context)

        self._emit(
            EventType.PLAN_CREATED,
            data={
                "plan_steps": [s.to_dict() for s in plan],
                "request_type": "bug_fix"
                if any(w in request_lower for w in ["fix", "crash", "bug", "error", "fail"])
                else "feature"
                if any(w in request_lower for w in ["implement", "add", "create", "new"])
                else "refactor"
                if any(w in request_lower for w in ["refactor", "simplify", "clean"])
                else "investigate",
            },
        )
        return plan

    def _run_iterative_loop(self, initial_plan: list[PlanStep]) -> dict[str, Any]:
        results = {
            "actions_taken": [],
            "tool_results": [],
            "iterations": 0,
            "stopped_reason": None,
        }

        plan = [PlanStep.from_dict(s) if isinstance(s, dict) else s for s in initial_plan]
        tool_results: list[ToolResult] = []

        capabilities = self.runtime.capabilities()
        supports_tool_calls = capabilities.get("tool_calls", False)
        supports_external_execution = capabilities.get("external_tool_execution", False)

        while self._iterations < self.config.max_iterations:
            if self._cancelled:
                results["stopped_reason"] = "cancelled"
                if self._current_task and not self._current_task.is_terminal():
                    try:
                        self._current_task.transition(
                            TaskState.CANCELLED, reason="cancelled_during_loop"
                        )
                        self._emit_state_changed(
                            self._current_task.current_state,
                            TaskState.CANCELLED,
                            reason="cancelled_during_loop",
                        )
                    except InvalidStateTransitionError:
                        pass
                break

            elapsed = time.time() - self._start_time
            if elapsed > self.config.max_runtime_seconds:
                results["stopped_reason"] = "timeout"
                if self._current_task:
                    try:
                        self._current_task.transition(TaskState.BLOCKED, reason="timeout")
                        self._emit_state_changed(
                            self._current_task.current_state, TaskState.BLOCKED, reason="timeout"
                        )
                    except InvalidStateTransitionError:
                        pass
                    self._emit(
                        EventType.RUNTIME_ERROR, data={"error": "timeout", "elapsed": elapsed}
                    )
                break

            if self._tools_used >= self.config.max_tool_calls:
                results["stopped_reason"] = "tool_limit"
                if self._current_task:
                    try:
                        self._current_task.transition(TaskState.BLOCKED, reason="tool_limit")
                        self._emit_state_changed(
                            self._current_task.current_state, TaskState.BLOCKED, reason="tool_limit"
                        )
                    except InvalidStateTransitionError:
                        pass
                break

            self._iterations += 1
            self._emit(EventType.ITERATION_STARTED, data={"iteration": self._iterations})

            context = ContextBuilder.build(
                self._current_task,
                getattr(self, "_available_skills", []),
                self._current_task.memory_context.get("results", []),
                [tr.to_dict() for tr in tool_results],
            )

            instructions = [
                "Work iteratively: analyze, act, observe, refine.",
                "For bug fixes: investigate first, then implement.",
            ]
            context["instructions"] = instructions

            try:
                self._emit(
                    EventType.MODEL_REQUEST_STARTED,
                    metadata={
                        "runtime": type(self.runtime).__name__,
                        "model": getattr(self.runtime, "model", None) or self.config.model,
                    },
                )
                response = self.runtime.respond(context)
                self._emit(
                    EventType.MODEL_RESPONSE_RECEIVED,
                    data={
                        "finish_reason": response.finish_reason.value
                        if response.finish_reason
                        else "stop",
                        "has_tool_calls": bool(response.tool_calls),
                        "content_length": len(response.content) if response.content else 0,
                    },
                )
            except Exception as e:
                logger.error(f"Runtime error: {e}")
                self._emit(EventType.MODEL_ERROR, data={"error": str(e)})
                self._emit(EventType.RUNTIME_ERROR, data={"error": str(e)})
                results["stopped_reason"] = "runtime_error"
                if self._current_task:
                    try:
                        self._current_task.transition(TaskState.FAILED, reason="runtime_error")
                        self._emit_state_changed(
                            self._current_task.current_state,
                            TaskState.FAILED,
                            reason="runtime_error",
                        )
                    except InvalidStateTransitionError:
                        pass
                break

            if not isinstance(response, RuntimeResponse):
                response = RuntimeResponse(
                    content=str(response) if response else "",
                    finish_reason=FinishReason.STOP,
                )

            if response.tool_calls and supports_tool_calls and supports_external_execution:
                try:
                    if self._current_task:
                        self._current_task.transition(
                            TaskState.WAITING_FOR_TOOL, reason="tool_calls_requested"
                        )
                        self._emit_state_changed(
                            TaskState.RUNNING,
                            TaskState.WAITING_FOR_TOOL,
                            reason="tool_calls_requested",
                        )
                except InvalidStateTransitionError:
                    pass

                for tool_call in response.tool_calls:
                    if self._tools_used >= self.config.max_tool_calls:
                        results["stopped_reason"] = "tool_limit"
                        if self._current_task:
                            try:
                                self._current_task.transition(
                                    TaskState.BLOCKED, reason="tool_limit"
                                )
                                self._emit_state_changed(
                                    self._current_task.current_state,
                                    TaskState.BLOCKED,
                                    reason="tool_limit",
                                )
                            except InvalidStateTransitionError:
                                pass
                        break

                    logger.info(f"Executing tool: {tool_call.tool}")
                    self._emit(
                        EventType.TOOL_CALL_STARTED,
                        data={
                            "tool": tool_call.tool,
                            "call_id": tool_call.id,
                            "arguments": tool_call.arguments,
                        },
                    )
                    start_time = time.time()
                    tool_result = self._tool_manager.execute(tool_call, cwd=self.project_path)
                    duration = time.time() - start_time
                    tool_results.append(tool_result)
                    self._tool_results.append(tool_result.to_dict())
                    self._tools_used += 1
                    logger.debug(f"Tool result: success={tool_result.success}")

                    event_type = (
                        EventType.TOOL_CALL_COMPLETED
                        if tool_result.success
                        else EventType.TOOL_CALL_FAILED
                    )
                    self._emit(
                        event_type,
                        data={
                            "tool": tool_call.tool,
                            "call_id": tool_call.id,
                            "success": tool_result.success,
                            "duration": round(duration, 3),
                            "exit_code": getattr(tool_result, "exit_code", None),
                        },
                    )

                    self._emit(
                        EventType.OBSERVATION_CREATED,
                        data={
                            "tool": tool_call.tool,
                            "success": tool_result.success,
                            "output_summary": (tool_result.output or "")[:200]
                            if tool_result.output
                            else "",
                        },
                    )

                if self._current_task:
                    try:
                        self._current_task.transition(
                            TaskState.OBSERVING, reason="tool_execution_complete"
                        )
                        self._emit_state_changed(
                            TaskState.WAITING_FOR_TOOL,
                            TaskState.OBSERVING,
                            reason="tool_execution_complete",
                        )
                    except InvalidStateTransitionError:
                        pass

                if self._should_replan_after_observation(tool_results):
                    if self._replan_count >= self.config.max_replans:
                        if self._current_task:
                            try:
                                self._current_task.transition(
                                    TaskState.FAILED, reason="max_replans_reached"
                                )
                                self._emit_state_changed(
                                    TaskState.OBSERVING,
                                    TaskState.FAILED,
                                    reason="max_replans_reached",
                                )
                            except InvalidStateTransitionError:
                                pass
                        break
                    try:
                        self._current_task.transition(
                            TaskState.REPLANNING, reason="tool_failure_replan"
                        )
                        self._emit_state_changed(
                            TaskState.OBSERVING, TaskState.REPLANNING, reason="tool_failure_replan"
                        )
                    except InvalidStateTransitionError:
                        pass
                    new_plan = self._replan(
                        tool_failures=[tr for tr in tool_results if not tr.success]
                    )
                    if new_plan is None:
                        if self._current_task:
                            try:
                                self._current_task.transition(
                                    TaskState.FAILED, reason="replan_failed"
                                )
                                self._emit_state_changed(
                                    TaskState.REPLANNING, TaskState.FAILED, reason="replan_failed"
                                )
                            except InvalidStateTransitionError:
                                pass
                        break
                    self._replan_count += 1
                    plan = [
                        PlanStep.from_dict(s.to_dict())
                        if isinstance(s, PlanStep)
                        else PlanStep.from_dict(s)
                        for s in new_plan
                    ]
                    self._current_task.plan = [s.to_dict() for s in plan]
                    try:
                        self._current_task.transition(TaskState.RUNNING, reason="replan_executing")
                        self._emit_state_changed(
                            TaskState.REPLANNING, TaskState.RUNNING, reason="replan_executing"
                        )
                    except InvalidStateTransitionError:
                        pass
                    continue

                try:
                    if self._current_task:
                        self._current_task.transition(
                            TaskState.RUNNING, reason="observation_complete"
                        )
                        self._emit_state_changed(
                            TaskState.OBSERVING, TaskState.RUNNING, reason="observation_complete"
                        )
                except InvalidStateTransitionError:
                    pass
                continue

            elif response.tool_calls:
                logger.error(
                    f"Runtime {type(self.runtime).__name__} returned tool_calls "
                    f"but capabilities declare tool_calls={supports_tool_calls}, "
                    f"external_tool_execution={supports_external_execution}. "
                    f"Failing task as contract violation."
                )
                self._emit(
                    EventType.RUNTIME_ERROR,
                    data={
                        "error": "runtime_contract_violation",
                        "runtime": type(self.runtime).__name__,
                        "tool_calls_capability": supports_tool_calls,
                        "external_tool_execution_capability": supports_external_execution,
                        "tool_calls_count": len(response.tool_calls),
                    },
                )
                results["stopped_reason"] = "runtime_contract_violation"
                if self._current_task:
                    try:
                        self._current_task.transition(
                            TaskState.FAILED, reason="runtime_contract_violation"
                        )
                        self._emit_state_changed(
                            self._current_task.current_state,
                            TaskState.FAILED,
                            reason="runtime_contract_violation",
                        )
                    except InvalidStateTransitionError:
                        pass
                break

            if response.is_complete:
                self._emit(
                    EventType.ITERATION_COMPLETED,
                    data={
                        "iteration": self._iterations,
                        "complete": True,
                        "tools_used_this_iteration": 0,
                    },
                )
                break

            self._emit(
                EventType.ITERATION_COMPLETED,
                data={
                    "iteration": self._iterations,
                    "complete": False,
                },
            )

        results["iterations"] = self._iterations
        results["tool_results"] = [tr.to_dict() for tr in tool_results]
        return results

    def _should_replan_after_observation(self, tool_results: list[ToolResult]) -> bool:
        return any(not tr.success for tr in tool_results)

    def _replan(
        self,
        tool_failures: list[ToolResult] | None = None,
        verification_failures: list[str] | None = None,
    ) -> list[PlanStep] | None:
        failed_tools = [tr.tool for tr in (tool_failures or []) if not tr.success]
        failed_verifications = verification_failures or []
        self._current_task.hypotheses.append(
            {
                "statement": (
                    f"Replanning due to failures: tools={failed_tools}, "
                    f"verifications={failed_verifications}"
                ),
                "supporting_evidence": [tr.error for tr in (tool_failures or []) if tr.error],
                "contradicting_evidence": [],
                "status": "PROPOSED",
            }
        )
        context = ContextBuilder.build(
            self._current_task,
            getattr(self, "_available_skills", []),
            self._current_task.memory_context.get("results", []),
            self._tool_results,
        )
        context["replan_context"] = {
            "failed_tools": failed_tools,
            "failed_verifications": failed_verifications,
            "replan_count": self._replan_count,
            "max_replans": self.config.max_replans,
        }
        context["instructions"] = [
            "Replan based on failures. Do not repeat previously failed steps.",
            "Focus on recovering from tool or verification failures.",
        ]
        try:
            response = self.runtime.respond(context)
            if hasattr(response, "content") and response.content:
                return [PlanStep(action="replan_continue", description=response.content[:200])]
        except Exception as e:
            logger.error(f"Replan runtime error: {e}")
        return None

    def _select_next_step(self, plan: list[PlanStep]) -> PlanStep | None:
        for step in plan:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def _adapt_plan(self, plan: list[PlanStep], tool_results: list[ToolResult]) -> list[PlanStep]:
        failed_tools = [tr for tr in tool_results if not tr.success]
        if failed_tools:
            self._current_task.hypotheses.append(
                {
                    "statement": f"Tools failed: {[t.tool for t in failed_tools]}",
                    "supporting_evidence": [t.error for t in failed_tools if t.error],
                    "contradicting_evidence": [],
                    "status": "PROPOSED",
                }
            )
        return plan

    def _execute_step(self, step: PlanStep) -> dict[str, Any]:
        result = {
            "step": step.action,
            "description": step.description,
            "outcome": None,
            "error": None,
        }
        try:
            if self._tools_used >= self.config.max_tool_calls:
                result["error"] = "Tool limit reached"
                return result
            context = ContextBuilder.build(
                self._current_task,
                getattr(self, "_available_skills", []),
                self._current_task.memory_context.get("results", []),
                self._tool_results,
            )
            action_result = self.runtime.respond(context)
            result["outcome"] = (
                action_result.to_dict() if hasattr(action_result, "to_dict") else str(action_result)
            )
            self._tools_used += 1
            logger.info(f"Completed step: {step.action}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Step {step.action} failed: {e}")
        return result

    def _store_task_memory(self, success: bool) -> None:
        if not self.memory or not self._current_task:
            return
        summary = (
            f"Completed {self._iterations} iterations, {self._tools_used} tools "
            f"used, verification: {'passed' if success else 'failed'}"
        )
        try:
            self.memory.store_task_result(
                task_id=self._current_task.task_id,
                user_request=self._current_task.user_request,
                success=success,
                summary=summary,
                project=self._current_task.project,
                iteration=self._iterations,
            )
        except Exception as e:
            logger.debug(f"Memory storage after task: {e}")

    def _run_verification(self, results: dict[str, Any]) -> dict[str, Any]:
        self._emit(
            EventType.VERIFICATION_STARTED,
            data={
                "flags": {
                    "format_check": self.config.run_format_check,
                    "build_check": self.config.run_build_check,
                    "tests": self.config.run_tests,
                }
            },
        )
        if not self.config.enable_verification:
            self._emit(EventType.VERIFICATION_COMPLETED, data={"passed": True, "skipped": True})
            return {
                "overall_passed": True,
                "format_check": None,
                "build_check": None,
                "test_results": None,
                "git_diff_check": None,
                "failures": [],
                "skipped": True,
            }

        scope = getattr(self.config, "verification_scope", "project")
        changed_files: list[str] | None = None

        if scope == "changed-files":
            current_changed = self._capture_changed_files()
            if current_changed is None or self._baseline_changed_files is None:
                logger.warning(
                    "Failed to capture changed files; falling back to project-wide verification"
                )
                scope = "project"
            else:
                delta = [f for f in current_changed if f not in self._baseline_changed_files]
                changed_files = delta if delta else []

        if scope == "changed-files" and not changed_files:
            self._emit(
                EventType.VERIFICATION_COMPLETED,
                data={"passed": True, "skipped": True, "reason": "no_changes"},
            )
            return {
                "overall_passed": True,
                "format_check": None,
                "build_check": None,
                "test_results": None,
                "git_diff_check": None,
                "failures": [],
                "skipped": True,
                "reason": "no_changes",
            }

        report = self._verifier.verify_all(
            run_format=self.config.run_format_check,
            run_build=self.config.run_build_check,
            run_tests=self.config.run_tests,
            changed_files=changed_files,
        )

        failures = report.to_dict()["failures"]
        for f in failures:
            logger.warning(f"Verification failure: {f}")

        self._emit(
            EventType.VERIFICATION_COMPLETED,
            data={
                "passed": report.to_dict().get("overall_passed", False),
                "skipped": False,
                "failure_count": len(failures),
            },
        )
        return report.to_dict()

    @property
    def current_task(self) -> Task | None:
        return self._current_task

    @property
    def tools_used(self) -> int:
        return self._tools_used

    @property
    def cancelled(self) -> bool:
        return self._cancelled


def create_agent(
    runtime: RuntimeAdapter,
    memory: MemoryManager,
    project_path: str | Path | None = None,
    config: AgentConfig | None = None,
    agentcore_config: AgentCoreConfig | None = None,
    event_bus: EventBus | None = None,
    persistence: TaskPersistenceManager | None = None,
) -> Agent:
    project = Path(project_path) if project_path else Path.cwd()
    core_config = agentcore_config or ConfigLoader.discover(project)
    if config is None:
        config = core_config.to_agent_config()
    return Agent(
        runtime=runtime,
        memory=memory,
        config=config,
        project_path=project_path,
        agentcore_config=core_config,
        event_bus=event_bus,
        persistence=persistence,
    )
