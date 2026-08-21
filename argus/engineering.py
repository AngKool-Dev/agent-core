"""Argus Engineering Loop v3.

Extends the existing Argus agent loop with explicit engineering phases:
  UNDERSTAND → INVESTIGATE → PLAN → EXECUTE → VERIFY → REVIEW → (REPAIR → VERIFY AGAIN)* → FINALIZE

The repair phase is model-driven: when verification fails, the model receives
the failure context and can autonomously apply fixes via tool calls.

The investigation phase gathers evidence before planning for non-trivial tasks.

Reuses existing ModelRouter, Memory, Skills, ProjectProfile, GitWorkflow,
Permissions, and Reliability controls.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from agentcore.runtimes.base import ToolResult

from argus.context import ProjectProfile
from argus.memory import ArgusMemory


class EngineeringPhase(str, Enum):
    UNDERSTAND = "UNDERSTAND"
    INVESTIGATE = "INVESTIGATE"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    REPLAN = "REPLAN"
    REVIEW = "REVIEW"
    REPAIR = "REPAIR"
    FINALIZE = "FINALIZE"


@dataclass
class EngineeringEvidence:
    phase: str
    command: str = ""
    success: bool = True
    output_summary: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "command": self.command,
            "success": self.success,
            "output_summary": self.output_summary,
            "timestamp": self.timestamp,
        }


@dataclass
class InvestigationEvidence:
    source: str
    action: str
    result_summary: str
    relevant_files: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "action": self.action,
            "result_summary": self.result_summary,
            "relevant_files": self.relevant_files,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class EngineeringTaskState:
    goal: str
    phase: EngineeringPhase = EngineeringPhase.UNDERSTAND
    plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    active_step: Optional[str] = None
    evidence: List[EngineeringEvidence] = field(default_factory=list)
    investigation_findings: List[InvestigationEvidence] = field(default_factory=list)
    verification_results: List[Dict[str, Any]] = field(default_factory=list)
    review_findings: List[str] = field(default_factory=list)
    repair_attempts: int = 0
    plan_revision_count: int = 0
    revised_plans: List[List[Dict[str, Any]]] = field(default_factory=list)
    final_status: Optional[str] = None
    modified_files: List[str] = field(default_factory=list)

    def add_evidence(self, phase: str, command: str = "", success: bool = True, output_summary: str = "") -> None:
        self.evidence.append(EngineeringEvidence(
            phase=phase,
            command=command,
            success=success,
            output_summary=output_summary,
        ))

    def add_investigation(self, source: str, action: str, result_summary: str, relevant_files: Optional[List[str]] = None, confidence: Optional[float] = None) -> None:
        self.investigation_findings.append(InvestigationEvidence(
            source=source,
            action=action,
            result_summary=result_summary,
            relevant_files=relevant_files or [],
            confidence=confidence,
        ))

    def record_revised_plan(self, plan: List[Dict[str, Any]]) -> None:
        self.revised_plans.append(plan)
        self.plan_revision_count = len(self.revised_plans)
        self.plan_steps = plan

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "phase": self.phase,
            "plan_steps": self.plan_steps,
            "completed_steps": self.completed_steps,
            "active_step": self.active_step,
            "evidence": [e.to_dict() for e in self.evidence[-10:]],
            "investigation_findings": [f.to_dict() for f in self.investigation_findings[-10:]],
            "verification_results": self.verification_results[-5:],
            "review_findings": self.review_findings[-10:],
            "repair_attempts": self.repair_attempts,
            "plan_revision_count": self.plan_revision_count,
            "revised_plans": self.revised_plans[-5:],
            "final_status": self.final_status,
            "modified_files": self.modified_files[-20:],
        }


@dataclass
class EngineeringLoopConfig:
    enabled: bool = False
    max_repair_attempts: int = 2
    max_plan_revisions: int = 2
    run_verification: bool = True
    run_format_check: bool = True
    run_build_check: bool = True
    run_tests: bool = True
    enable_investigation: bool = True


def should_enter_engineering_loop(request: str, tool_results: List[Any]) -> bool:
    request_lower = request.lower()
    code_modifying_tools = {"write_file", "edit_file", "bash"}
    has_code_modification = False
    for r in tool_results:
        if isinstance(r, dict):
            tool = r.get("tool", "")
            success = r.get("success", False)
        else:
            tool = getattr(r, "tool", "")
            success = getattr(r, "success", False)
        if tool in code_modifying_tools and success:
            has_code_modification = True
            break

    engineering_keywords = ["fix", "bug", "error", "implement", "add", "create", "refactor", "improve"]
    is_engineering_task = any(kw in request_lower for kw in engineering_keywords)
    return is_engineering_task and has_code_modification


def select_verification_commands(project_profile: ProjectProfile, config: EngineeringLoopConfig) -> List[str]:
    commands: List[str] = []
    if not config.run_verification:
        return commands

    test_command = project_profile.test_command
    if test_command and config.run_tests:
        commands.append(test_command)

    formatter = project_profile.formatter_command
    if formatter and config.run_format_check:
        if formatter == "black":
            commands.append("black --check .")
        elif formatter == "prettier":
            commands.append("prettier --check .")
        elif formatter == "cargo fmt":
            commands.append("cargo fmt -- --check")
        elif formatter == "gofmt":
            commands.append("gofmt -l .")

    linter = project_profile.linter_command
    if linter and config.run_format_check:
        if linter == "ruff":
            commands.append("ruff check .")
        elif linter == "flake8":
            commands.append("flake8 .")
        elif linter == "eslint":
            commands.append("eslint .")
        elif linter == "cargo clippy":
            commands.append("cargo clippy")
        elif linter == "go vet":
            commands.append("go vet ./...")

    return commands


def extract_modified_files(tool_results: List[Any]) -> List[str]:
    modified: List[str] = []
    for result in tool_results:
        if isinstance(result, dict):
            tool = result.get("tool", "")
            success = result.get("success", False)
            output = result.get("output", "")
            metadata = result.get("metadata", {})
        else:
            tool = getattr(result, "tool", "")
            success = getattr(result, "success", False)
            output = getattr(result, "output", "")
            metadata = getattr(result, "metadata", {})

        if success and tool in ("write_file", "edit_file"):
            path = metadata.get("path")
            if not path and output:
                parts = output.split()
                for part in parts:
                    if part.startswith("to ") or part.startswith("in ") or part.startswith("Edited "):
                        path = part[3:] if part.startswith("to ") else (part[3:] if part.startswith("in ") else part[7:])
                        break
            if path:
                modified.append(path)
    return modified


def is_trivial_request(request: str) -> bool:
    request_lower = request.lower()
    trivial_indicators = [
        "what's in", "what is in", "show me", "read ", "list ", "cat ",
        "what's the", "what is the", "what is ", "tell me about", "explain ",
        "hello", "hi ", "hey", "test",
    ]
    for indicator in trivial_indicators:
        if request_lower.startswith(indicator):
            return True
    if len(request.split()) <= 2 and not any(kw in request_lower for kw in ["fix", "bug", "error", "implement", "add", "create", "refactor", "improve"]):
        return True
    return False

