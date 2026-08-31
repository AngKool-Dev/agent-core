"""Adaptive agent loop - OBSERVE→UNDERSTAND→DECIDE→ACT→VERIFY→RECOVER."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from argus.capabilities import (
    Capability,
    CapabilityExecution,
    CapabilityRegistry,
    CapabilityRouter,
    CapabilityType,
)
from argus.capabilities.context_engine import ContextEngine, ContextAnalysis
from argus.capabilities.repo_map import RepoMap, RepositoryMapper


class AgentPhase(str, Enum):
    OBSERVE = "observe"
    UNDERSTAND = "understand"
    DECIDE = "decide"
    ACT = "act"
    VERIFY = "verify"
    RECOVER = "recover"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class AgentObservation:
    """Observation from the OBSERVE phase."""
    query: str
    project_path: str = ""
    repo_map: Optional[RepoMap] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentDecision:
    """Decision from the DECIDE phase."""
    capability_id: str
    input_data: Dict[str, Any]
    confidence: float = 0.0
    alternatives: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class AgentActionResult:
    """Result from the ACT phase."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    capability_id: str = ""
    fallback_used: bool = False


@dataclass
class AgentVerification:
    """Verification from the VERIFY phase."""
    passed: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentStep:
    """A single step in the agent loop."""
    phase: AgentPhase
    timestamp: float = field(default_factory=time.time)
    data: Any = None
    duration: float = 0.0


@dataclass
class AgentTrace:
    """Trace of the entire agent loop execution."""
    query: str
    steps: List[AgentStep] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    final_result: Optional[AgentActionResult] = None
    success: bool = False

    @property
    def total_duration(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def add_step(self, phase: AgentPhase, data: Any = None, duration: float = 0.0) -> None:
        self.steps.append(AgentStep(phase=phase, data=data, duration=duration))


class AdaptiveAgentLoop:
    """Adaptive agent loop implementing OBSERVE→UNDERSTAND→DECIDE→ACT→VERIFY→RECOVER."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        router: Optional[CapabilityRouter] = None,
        context_engine: Optional[ContextEngine] = None,
        max_iterations: int = 10,
        max_recovers: int = 3,
        enable_verification: bool = True,
    ):
        self._registry = registry
        self._router = router or CapabilityRouter(registry)
        self._context_engine = context_engine or ContextEngine(registry)
        self._max_iterations = max_iterations
        self._max_recovers = max_recovers
        self._enable_verification = enable_verification
        self._repo_mapper = RepositoryMapper()

    def execute(self, query: str, project_path: str = "") -> AgentTrace:
        """Execute the full adaptive agent loop."""
        trace = AgentTrace(query=query)

        try:
            # OBSERVE
            observation = self._observe(query, project_path, trace)

            # UNDERSTAND
            analysis = self._understand(observation, trace)

            # DECIDE
            decision = self._decide(analysis, trace)

            # ACT
            result = self._act(decision, trace)

            # VERIFY
            if self._enable_verification:
                verification = self._verify(result, observation, trace)

                # RECOVER (if needed)
                if not verification.passed:
                    result = self._recover(result, decision, analysis, trace)

            trace.final_result = result
            trace.success = result.success if result else False

        except Exception as e:
            trace.add_step(AgentPhase.FAILED, data={"error": str(e)})
            trace.final_result = AgentActionResult(success=False, error=str(e))

        trace.end_time = time.time()
        return trace

    def _observe(self, query: str, project_path: str, trace: AgentTrace) -> AgentObservation:
        """OBSERVE phase - gather context."""
        start = time.time()

        observation = AgentObservation(
            query=query,
            project_path=project_path,
        )

        # Build repo map if project path exists
        if project_path:
            try:
                observation.repo_map = self._repo_mapper.map_repository(project_path)
            except Exception:
                pass  # Repo map is optional

        # Gather context from observation
        observation.context = {
            "has_repo_map": observation.repo_map is not None,
            "total_files": observation.repo_map.total_files if observation.repo_map else 0,
            "languages": observation.repo_map.languages if observation.repo_map else {},
        }

        trace.add_step(AgentPhase.OBSERVE, data=observation, duration=time.time() - start)
        return observation

    def _understand(self, observation: AgentObservation, trace: AgentTrace) -> ContextAnalysis:
        """UNDERSTAND phase - analyze the query."""
        start = time.time()

        analysis = self._context_engine.analyze(observation.query)

        trace.add_step(AgentPhase.UNDERSTAND, data=analysis, duration=time.time() - start)
        return analysis

    def _decide(self, analysis: ContextAnalysis, trace: AgentTrace) -> AgentDecision:
        """DECIDE phase - select the best capability."""
        start = time.time()

        if not analysis.suggested_capabilities:
            return AgentDecision(
                capability_id="",
                input_data={},
                confidence=0.0,
                reasoning="No capabilities matched the query",
            )

        # Select top capability
        top = analysis.suggested_capabilities[0]
        alternatives = [s.capability_id for s in analysis.suggested_capabilities[1:4]]

        # Build input data based on capability type
        input_data = self._build_input_data(top.capability_id, analysis)

        decision = AgentDecision(
            capability_id=top.capability_id,
            input_data=input_data,
            confidence=top.score,
            alternatives=alternatives,
            reasoning=f"Selected based on score {top.score:.2f} with reasons: {', '.join(top.reasons)}",
        )

        trace.add_step(AgentPhase.DECIDE, data=decision, duration=time.time() - start)
        return decision

    def _act(self, decision: AgentDecision, trace: AgentTrace) -> AgentActionResult:
        """ACT phase - execute the selected capability."""
        start = time.time()

        if not decision.capability_id:
            return AgentActionResult(
                success=False,
                error="No capability selected",
                execution_time=time.time() - start,
            )

        # Execute via router
        result = self._router.route(decision.capability_id, decision.input_data)

        action_result = AgentActionResult(
            success=result.get("success", False),
            output=result.get("output"),
            error=result.get("error"),
            execution_time=result.get("execution_time", time.time() - start),
            capability_id=decision.capability_id,
            fallback_used=result.get("fallback_used", False),
        )

        trace.add_step(AgentPhase.ACT, data=action_result, duration=time.time() - start)
        return action_result

    def _verify(
        self,
        result: AgentActionResult,
        observation: AgentObservation,
        trace: AgentTrace,
    ) -> AgentVerification:
        """VERIFY phase - check the result."""
        start = time.time()

        if result.success:
            verification = AgentVerification(
                passed=True,
                message="Action completed successfully",
                details={"capability": result.capability_id},
            )
        else:
            verification = AgentVerification(
                passed=False,
                message=f"Action failed: {result.error}",
                details={"capability": result.capability_id, "error": result.error},
            )

        trace.add_step(AgentPhase.VERIFY, data=verification, duration=time.time() - start)
        return verification

    def _recover(
        self,
        result: AgentActionResult,
        decision: AgentDecision,
        analysis: ContextAnalysis,
        trace: AgentTrace,
    ) -> AgentActionResult:
        """RECOVER phase - try alternatives on failure."""
        start = time.time()

        for attempt in range(self._max_recovers):
            if not decision.alternatives:
                break

            # Try next alternative
            alt_id = decision.alternatives.pop(0)
            alt_input = self._build_input_data(alt_id, analysis)

            alt_result = self._router.route(alt_id, alt_input)

            if alt_result.get("success"):
                recovery_result = AgentActionResult(
                    success=True,
                    output=alt_result.get("output"),
                    execution_time=alt_result.get("execution_time", 0),
                    capability_id=alt_id,
                    fallback_used=True,
                )
                trace.add_step(
                    AgentPhase.RECOVER,
                    data={"attempt": attempt + 1, "capability": alt_id, "success": True},
                    duration=time.time() - start,
                )
                return recovery_result

            trace.add_step(
                AgentPhase.RECOVER,
                data={"attempt": attempt + 1, "capability": alt_id, "success": False},
            )

        # All recoveries failed
        trace.add_step(
            AgentPhase.RECOVER,
            data={"attempts": self._max_recovers, "success": False},
            duration=time.time() - start,
        )
        return result

    def _build_input_data(self, capability_id: str, analysis: ContextAnalysis) -> Dict[str, Any]:
        """Build input data for a capability based on analysis."""
        input_data: Dict[str, Any] = {}

        # Extract relevant parameters from query
        query = analysis.query.lower()

        if capability_id.startswith("filesystem."):
            if capability_id == "filesystem.read":
                input_data["path"] = self._extract_path(query) or ""
            elif capability_id == "filesystem.write":
                input_data["path"] = self._extract_path(query) or ""
                input_data["content"] = ""
            elif capability_id == "filesystem.edit":
                input_data["path"] = self._extract_path(query) or ""
                input_data["old_string"] = ""
                input_data["new_string"] = ""
            elif capability_id == "filesystem.list_dir":
                input_data["path"] = self._extract_path(query) or "."

        elif capability_id == "shell.execute":
            input_data["command"] = self._extract_command(query) or analysis.query

        elif capability_id.startswith("search."):
            if capability_id == "search.grep":
                input_data["pattern"] = self._extract_pattern(query) or ""
                input_data["path"] = self._extract_path(query) or "."
            elif capability_id == "search.glob":
                input_data["pattern"] = self._extract_pattern(query) or "*"

        elif capability_id.startswith("git."):
            if capability_id == "git.add":
                input_data["paths"] = []
            elif capability_id == "git.commit":
                input_data["message"] = "Auto commit"

        elif capability_id.startswith("web."):
            if capability_id == "web.read":
                input_data["url"] = self._extract_url(analysis.query) or ""
            elif capability_id == "web.search":
                input_data["query"] = analysis.query

        elif capability_id.startswith("github."):
            if capability_id == "github.search_repos":
                input_data["query"] = analysis.query
            elif capability_id == "github.get_repo":
                input_data["owner"] = ""
                input_data["repo"] = ""

        elif capability_id.startswith("youtube."):
            if capability_id == "youtube.search":
                input_data["query"] = analysis.query
            elif capability_id == "youtube.get_info":
                input_data["video_id"] = self._extract_youtube_id(analysis.query) or ""

        elif capability_id.startswith("reddit."):
            if capability_id == "reddit.search":
                input_data["query"] = analysis.query
            elif capability_id == "reddit.get_subreddit":
                input_data["subreddit"] = ""

        return input_data

    def _extract_path(self, query: str) -> Optional[str]:
        """Extract file path from query."""
        import re
        # Match common path patterns
        patterns = [
            r"(?:file|path|in)\s+[\"']?([./\\]\S+?)[\"']?(?:\s|$)",
            r"(?:read|open|show|edit|modify)\s+[\"']?([./\\]\S+\.\w+)[\"']?",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_command(self, query: str) -> Optional[str]:
        """Extract shell command from query."""
        import re
        patterns = [
            r"(?:run|execute)\s+command\s+[\"']([^\"']+)[\"']",
            r"!\s*(\S.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_pattern(self, query: str) -> Optional[str]:
        """Extract search pattern from query."""
        import re
        patterns = [
            r"(?:pattern|for)\s+[\"']([^\"']+)[\"']",
            r"(?:search|find|grep)\s+(?:for\s+)?[\"']?(\w+)[\"']?",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_url(self, query: str) -> Optional[str]:
        """Extract URL from query."""
        import re
        match = re.search(r"(https?://\S+)", query)
        return match.group(1) if match else None

    def _extract_youtube_id(self, query: str) -> Optional[str]:
        """Extract YouTube video ID from query."""
        import re
        patterns = [
            r"youtu\.be/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(1)
        return None


def create_adaptive_loop(
    registry: CapabilityRegistry,
    **kwargs,
) -> AdaptiveAgentLoop:
    """Create an adaptive agent loop with the given registry."""
    router = CapabilityRouter(registry)
    context_engine = ContextEngine(registry)
    return AdaptiveAgentLoop(
        registry=registry,
        router=router,
        context_engine=context_engine,
        **kwargs,
    )