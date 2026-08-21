import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context import ProjectContext
from .memory import MemoryManager
from .planner import Planner, PlanStep
from .router import RoutingResult, SkillRouter
from .runtimes.base import RuntimeAdapter, ToolCall, ToolResult
from .skills import Skill, SkillRegistry
from .task import Task, TaskState
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
    max_consecutive_failures: int = 3
    max_no_progress: int = 3
    enable_verification: bool = True
    run_format_check: bool = True
    run_build_check: bool = True
    run_tests: bool = True


class ContextBuilder:
    @staticmethod
    def build(
        task: Task,
        skills: list[Skill],
        memory_results: list[dict],
        tool_results: list[dict],
    ) -> dict[str, Any]:
        return {
            "task": task.to_dict(),
            "project_context": task.project_context,
            "memory": memory_results,
            "skills": task.selected_skills,
            "tool_results": tool_results,
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
    ):
        self.runtime = runtime
        self.memory = memory
        self.config = config or AgentConfig()
        self.project_path = Path(project_path) if project_path else Path.cwd()

        self._tool_manager = ToolManager(self.project_path)
        self._verifier = Verifier(self.project_path)
        self._planner = Planner()

        self._current_task: Task | None = None
        self._iterations = 0
        self._tools_used = 0
        self._tool_results: list[dict[str, Any]] = []
        self._start_time = 0
        self._consecutive_failures = 0
        self._no_progress_count = 0
        self._last_batch_calls: list[str] = []
        self._cancelled = False

    def execute(self, user_request: str, project: str | None = None) -> dict[str, Any]:
        import time

        self._start_time = time.time()
        self._iterations = 0
        self._tools_used = 0
        self._tool_results = []
        self._consecutive_failures = 0
        self._no_progress_count = 0
        self._last_batch_calls = []
        self._cancelled = False

        self._current_task = Task(
            user_request=user_request,
            project=project or str(self.project_path),
        )
        self._current_task.update_state(TaskState.ANALYZING)
        logger.info(f"Task created: {self._current_task.task_id}")

        project_context = self._load_project_context()
        self._current_task.project_context = project_context

        memory_results = self._load_memory_context()
        self._current_task.memory_context = {
            "results": memory_results,
            "count": len(memory_results),
        }

        self._current_task.update_state(TaskState.ROUTING)
        routing = self._route_skills(user_request, project_context)
        self._current_task.selected_skills = routing.selected_skills
        self._current_task.attributes = routing.attributes
        logger.info(f"Selected skills: {routing.selected_skills}")

        self._current_task.update_state(TaskState.INVESTIGATING)
        investigation = self._investigate(user_request)
        self._current_task.hypotheses.append(investigation)

        self._current_task.update_state(TaskState.PLANNING)
        plan = self._generate_plan(user_request, project_context)
        self._current_task.plan = [s.to_dict() for s in plan]

        self._current_task.update_state(TaskState.IMPLEMENTING)
        results = self._run_iterative_loop(plan)

        self._current_task.update_state(TaskState.VERIFYING)
        verification = self._run_verification(results)

        if verification["overall_passed"] and results.get("status") != "FAILED":
            self._current_task.update_state(TaskState.COMPLETED)
        else:
            self._current_task.update_state(TaskState.FAILED)

        logger.info(f"Task completed with state: {self._current_task.current_state}")

        return {
            "task": self._current_task.to_dict(),
            "verification": verification,
            "success": verification["overall_passed"]
            and results.get("status") != "FAILED",
            "tools_used": self._tools_used,
            "iterations": self._iterations,
            "status": results.get("status", "COMPLETED"),
            "stopped_reason": results.get("stopped_reason"),
            "observations": results.get("observations", []),
        }

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

        try:
            results = self.memory.search(query, self._current_task.project, limit=10)
            return results
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
            return []

    def _route_skills(self, prompt: str, context: dict[str, Any]) -> RoutingResult:
        skill_paths = []
        registry = SkillRegistry(skill_paths)
        skills = registry.discover(skill_paths)

        self._skill_registry = registry
        self._available_skills = skills

        router = SkillRouter(skills)
        result = router.route(prompt, context)

        loaded_skills = []
        for skill_name in result.selected_skills:
            skill = registry.find(skill_name)
            if skill:
                loaded_skills.append(skill)

        result.loaded_skills = loaded_skills
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

        if any(
            word in request_lower for word in ["fix", "crash", "bug", "error", "fail"]
        ):
            return self._planner.plan("bug_fix", request, context)

        if any(word in request_lower for word in ["implement", "add", "create", "new"]):
            return self._planner.plan("feature_implement", request, context)

        if any(word in request_lower for word in ["refactor", "simplify", "clean"]):
            return self._planner.plan("refactor", request, context)

        if any(
            word in request_lower for word in ["investigate", "explain", "why", "what"]
        ):
            return [
                PlanStep(
                    action="investigate",
                    description="Explore the codebase to understand the request",
                ),
                PlanStep(
                    action="summarize", description="Summarize findings for the user"
                ),
            ]

        return self._planner.plan("investigate", request, context)

    def _run_iterative_loop(self, initial_plan: list[PlanStep]) -> dict[str, Any]:
        results = {
            "actions_taken": [],
            "tool_results": [],
            "iterations": 0,
            "stopped_reason": None,
            "status": "RUNNING",
            "observations": [],
        }

        plan = list(initial_plan)
        tool_results: list[ToolResult] = []

        while self._iterations < self.config.max_iterations:
            elapsed = time.time() - self._start_time
            if elapsed > self.config.max_runtime_seconds:
                results["status"] = "TIMEOUT"
                results["stopped_reason"] = "timeout"
                self._current_task.update_state(TaskState.BLOCKED)
                break

            if self._tools_used >= self.config.max_tool_calls:
                results["status"] = "TOOL_LIMIT"
                results["stopped_reason"] = "tool_limit"
                self._current_task.update_state(TaskState.BLOCKED)
                break

            if self._consecutive_failures >= self.config.max_consecutive_failures:
                results["status"] = "FAILED"
                results["stopped_reason"] = "consecutive_tool_failures"
                self._current_task.update_state(TaskState.FAILED)
                break

            if self._cancelled:
                results["status"] = "CANCELLED"
                results["stopped_reason"] = "user_cancellation"
                self._current_task.update_state(TaskState.FAILED)
                break

            context = ContextBuilder.build(
                self._current_task,
                getattr(self, "_loaded_skills", []),
                self._current_task.memory_context.get("results", []),
                [tr.to_dict() if hasattr(tr, "to_dict") else tr for tr in tool_results],
            )

            instructions = [
                "Work iteratively: analyze, act, observe, refine.",
                "For bug fixes: investigate first, then implement.",
            ]
            context["instructions"] = instructions

            try:
                runtime_response = self.runtime.respond(context)
            except Exception as e:
                logger.error(f"Runtime error: {e}")
                results["status"] = "RUNTIME_ERROR"
                results["stopped_reason"] = "runtime_error"
                self._current_task.update_state(TaskState.FAILED)
                break

            if isinstance(runtime_response, dict):
                if runtime_response.get("complete"):
                    results["status"] = "COMPLETED"
                    break
                tool_calls = runtime_response.get("tool_calls", [])
                if not tool_calls and not self._response_contains_final_answer(
                    runtime_response.get("response", "")
                ):
                    continue
            elif isinstance(runtime_response, str):
                pass
            else:
                continue

            batch_results: list[ToolResult] = []

            pending_tool = getattr(
                self.runtime, "get_pending_tool_call", lambda: None
            )()
            if pending_tool:
                if self._tools_used < self.config.max_tool_calls:
                    tool_result = self._execute_tool_call(pending_tool)
                    batch_results.append(tool_result)
                    tool_results.append(tool_result)
                    self._tool_results.append(tool_result.to_dict())
                    self._tools_used += 1

                if hasattr(self.runtime, "clear_tool_call"):
                    self.runtime.clear_tool_call()
            elif tool_calls:
                for tc in tool_calls:
                    if self._tools_used >= self.config.max_tool_calls:
                        break
                    tool_result = self._execute_tool_call(tc)
                    batch_results.append(tool_result)
                    tool_results.append(tool_result)
                    self._tool_results.append(tool_result.to_dict())
                    self._tools_used += 1

            if hasattr(self.runtime, "is_complete") and self.runtime.is_complete():
                results["status"] = "COMPLETED"
                break

            observation = self._observe_tool_batch(tool_results)
            results["observations"].append(observation)

            failures = [tr for tr in tool_results if not tr.success]
            if failures:
                self._consecutive_failures += 1
            else:
                self._consecutive_failures = 0

            current_batch_calls = [tr.tool for tr in batch_results]
            if current_batch_calls == self._last_batch_calls and current_batch_calls:
                self._no_progress_count += 1
            else:
                self._no_progress_count = 0
            self._last_batch_calls = current_batch_calls

            if self._no_progress_count >= self.config.max_no_progress:
                results["status"] = "FAILED"
                results["stopped_reason"] = "no_progress"
                self._current_task.update_state(TaskState.FAILED)
                break

            plan = self._adapt_plan(plan, tool_results)
            next_step = self._select_next_step(plan)

            if not next_step:
                results["status"] = "COMPLETED"
                break

            step_result = self._execute_step(next_step)
            results["actions_taken"].append(step_result)
            self._iterations += 1

        results["iterations"] = self._iterations
        if results["status"] == "RUNNING":
            results["status"] = "COMPLETED"
        return results

    def _response_contains_final_answer(self, response: str) -> bool:
        if not response:
            return False
        response_lower = response.lower()
        return (
            "final answer:" in response_lower
            or "complete:" in response_lower
            or response_lower.startswith("the fix")
        )

    def _observe_tool_batch(self, tool_results: list[ToolResult]) -> str:
        if not tool_results:
            return "No tools executed"

        successes = [r for r in tool_results if r.success]
        failures = [r for r in tool_results if not r.success]

        parts = [
            f"{len(successes)} succeeded, {len(failures)} failed",
        ]

        if failures:
            errors = [r.error for r in failures[:3] if r.error]
            if errors:
                parts.append(f"Errors: {'; '.join(errors)}")

        output_preview = ""
        for r in successes:
            if r.stdout:
                output_preview = r.stdout[:200]
                break

        if output_preview:
            parts.append(f"Output preview: {output_preview}")

        return ". ".join(parts)

    def cancel(self) -> None:
        self._cancelled = True

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        logger.info(f"Executing tool: {tool_call.tool}")
        try:
            result = self.runtime.execute_tool(tool_call, self.project_path)
            logger.debug(f"Tool result: success={result.success}")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return ToolResult(
                success=False,
                tool=tool_call.tool,
                error=str(e),
            )

    def _select_next_step(self, plan: list[PlanStep]) -> PlanStep | None:
        for step in plan:
            if step.action not in [
                s.get("completed", False)
                for s in getattr(self._current_task, "actions", [])
            ]:
                return step
        return None

    def _adapt_plan(
        self, plan: list[PlanStep], tool_results: list[ToolResult]
    ) -> list[PlanStep]:
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
        logger.info(f"Step {step.action} completed")
        return result

    def _run_verification(self, results: dict[str, Any]) -> dict[str, Any]:
        if not self.config.enable_verification:
            return {"overall_passed": True}

        report = self._verifier.verify_all(
            run_format=self.config.run_format_check,
            run_build=self.config.run_build_check,
            run_tests=self.config.run_tests,
        )

        failures = report.to_dict()["failures"]
        for f in failures:
            logger.warning(f"Verification failure: {f}")

        return report.to_dict()

    @property
    def current_task(self) -> Task | None:
        return self._current_task

    @property
    def tools_used(self) -> int:
        return self._tools_used

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def no_progress_count(self) -> int:
        return self._no_progress_count


def create_agent(
    runtime: RuntimeAdapter,
    memory: MemoryManager,
    project_path: str | Path | None = None,
    config: AgentConfig | None = None,
) -> Agent:
    return Agent(
        runtime=runtime, memory=memory, config=config, project_path=project_path
    )
