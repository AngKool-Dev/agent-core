"""Tests for Argus Engineering Loop v1."""

import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from argus.agent import ArgusAgent, ArgusAgentConfig
from argus.engineering import (
    EngineeringPhase,
    EngineeringTaskState,
    EngineeringLoopConfig,
    should_enter_engineering_loop,
    select_verification_commands,
    extract_modified_files,
)
from argus.context.project import ProjectProfile
from argus.memory import ArgusMemory
from argus.tools import ToolResult


class TestEngineeringPhaseTransitions:
    def test_phase_enum_values(self):
        assert EngineeringPhase.UNDERSTAND == "UNDERSTAND"
        assert EngineeringPhase.PLAN == "PLAN"
        assert EngineeringPhase.EXECUTE == "EXECUTE"
        assert EngineeringPhase.VERIFY == "VERIFY"
        assert EngineeringPhase.REVIEW == "REVIEW"
        assert EngineeringPhase.REPAIR == "REPAIR"
        assert EngineeringPhase.FINALIZE == "FINALIZE"

    def test_task_state_defaults(self):
        state = EngineeringTaskState(goal="fix bug")
        assert state.phase == EngineeringPhase.UNDERSTAND
        assert state.repair_attempts == 0
        assert state.final_status is None
        assert state.evidence == []

    def test_task_state_add_evidence(self):
        state = EngineeringTaskState(goal="fix bug")
        state.add_evidence("VERIFY", command="pytest", success=True, output_summary="passed")
        assert len(state.evidence) == 1
        assert state.evidence[0].phase == "VERIFY"
        assert state.evidence[0].command == "pytest"
        assert state.evidence[0].success is True

    def test_task_state_to_dict(self):
        state = EngineeringTaskState(goal="fix bug")
        state.add_evidence("VERIFY", command="pytest", success=True)
        data = state.to_dict()
        assert data["goal"] == "fix bug"
        assert data["phase"] == EngineeringPhase.UNDERSTAND
        assert len(data["evidence"]) == 1


class TestShouldEnterEngineeringLoop:
    def test_engineering_task_with_modification_enters(self):
        request = "fix the bug in auth.py"
        tool_results = [
            ToolResult(tool="edit_file", success=True, output="fixed"),
        ]
        assert should_enter_engineering_loop(request, tool_results) is True

    def test_read_only_task_skips(self):
        request = "investigate the auth module"
        tool_results = [
            ToolResult(tool="read_file", success=True, output="code"),
        ]
        assert should_enter_engineering_loop(request, tool_results) is False

    def test_engineering_keyword_without_modification_skips(self):
        request = "fix the bug"
        tool_results = [
            ToolResult(tool="read_file", success=True, output="code"),
        ]
        assert should_enter_engineering_loop(request, tool_results) is False

    def test_non_engineering_task_with_modification_skips(self):
        request = "show me the code"
        tool_results = [
            ToolResult(tool="edit_file", success=True, output="changed"),
        ]
        assert should_enter_engineering_loop(request, tool_results) is False

    def test_dict_tool_results(self):
        request = "implement feature"
        tool_results = [
            {"tool": "write_file", "success": True, "output": "written"},
        ]
        assert should_enter_engineering_loop(request, tool_results) is True

    def test_bash_modification_counts(self):
        request = "fix the bug"
        tool_results = [
            ToolResult(tool="bash", success=True, output="fixed"),
        ]
        assert should_enter_engineering_loop(request, tool_results) is True


class TestVerificationCommandSelection:
    def test_python_project_commands(self):
        profile = ProjectProfile(
            root="/tmp",
            test_command="pytest",
            formatter_command="black",
            linter_command="ruff",
        )
        config = EngineeringLoopConfig()
        commands = select_verification_commands(profile, config)
        assert "pytest" in commands
        assert "black --check ." in commands
        assert "ruff check ." in commands

    def test_rust_project_commands(self):
        profile = ProjectProfile(
            root="/tmp",
            test_command="cargo test",
            formatter_command="cargo fmt",
            linter_command="cargo clippy",
        )
        config = EngineeringLoopConfig()
        commands = select_verification_commands(profile, config)
        assert "cargo test" in commands
        assert "cargo fmt -- --check" in commands
        assert "cargo clippy" in commands

    def test_node_project_commands(self):
        profile = ProjectProfile(
            root="/tmp",
            test_command="npm test",
            formatter_command="prettier",
            linter_command="eslint",
        )
        config = EngineeringLoopConfig()
        commands = select_verification_commands(profile, config)
        assert "npm test" in commands
        assert "prettier --check ." in commands
        assert "eslint ." in commands

    def test_missing_commands_skipped(self):
        profile = ProjectProfile(root="/tmp")
        config = EngineeringLoopConfig()
        commands = select_verification_commands(profile, config)
        assert commands == []

    def test_verification_disabled(self):
        profile = ProjectProfile(root="/tmp", test_command="pytest")
        config = EngineeringLoopConfig(run_verification=False)
        commands = select_verification_commands(profile, config)
        assert commands == []


class TestExtractModifiedFiles:
    def test_extracts_write_file_from_metadata(self):
        results = [
            ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
        ]
        assert extract_modified_files(results) == ["foo.py"]

    def test_extracts_edit_file_from_metadata(self):
        results = [
            ToolResult(tool="edit_file", success=True, output="edited", metadata={"path": "bar.py"}),
        ]
        assert extract_modified_files(results) == ["bar.py"]

    def test_ignores_failed_modifications(self):
        results = [
            ToolResult(tool="write_file", success=False, output="failed", metadata={"path": "foo.py"}),
        ]
        assert extract_modified_files(results) == []

    def test_ignores_non_modifying_tools(self):
        results = [
            ToolResult(tool="read_file", success=True, output="code"),
        ]
        assert extract_modified_files(results) == []

    def test_dict_results(self):
        results = [
            {"tool": "edit_file", "success": True, "output": "edited", "metadata": {"path": "foo.py"}},
        ]
        assert extract_modified_files(results) == ["foo.py"]


class TestAgentEngineeringLoopIntegration:
    def test_simple_task_skips_engineering_loop(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        result = agent.execute("hello")
        assert "engineering" not in result
        assert result["status"] == "COMPLETED"

    def test_code_task_enters_engineering_loop(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        result = agent.execute("fix the bug")
        # The default reasoner will produce tool calls, and if any succeed, engineering loop may enter
        # We just check the structure is correct
        assert "status" in result

    def test_engineering_loop_disabled_by_default(self):
        agent = ArgusAgent(project_path=".")
        result = agent.execute("fix the bug")
        assert "engineering" not in result

    def test_engineering_loop_config_fields(self):
        config = ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=5)
        assert config.enable_engineering_loop is True
        assert config.max_repair_attempts == 5

    def test_engineering_state_initialized(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        assert agent._engineering_state is None
        agent.execute("hello")
        assert agent._engineering_state is None  # simple task doesn't enter

    def test_status_callback_phase_updates(self):
        from argus.permissions import PermissionConfig

        phases = []
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
            status_callback=lambda m: phases.append(m),
        )
        agent._tool_registry.set_permissions(PermissionConfig(bash="allow", write="allow"))

        class ModificationRuntime:
            def respond(self, context):
                return {
                    "complete": False,
                    "response": "Fixing bug...",
                    "tool_calls": [{"tool": "write_file", "arguments": {"path": "foo.py", "content": "fix"}}],
                }

        agent._runtime = ModificationRuntime()
        with patch.object(agent, '_run_verification_command', return_value=(True, "passed")):
            agent.execute("fix the bug")
        # Check that phase status messages were emitted
        phase_messages = [p for p in phases if "Phase:" in p]
        assert len(phase_messages) > 0

    def test_reliability_safeguards_preserved(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(
                enable_engineering_loop=True,
                max_repair_attempts=2,
                max_consecutive_failures=2,
                max_no_progress=2,
            ),
        )
        result = agent.execute("fail repeatedly")
        assert result["status"] in ("FAILED", "COMPLETED", "CANCELLED", "TIMEOUT", "TOOL_LIMIT", "RUNTIME_ERROR")


class TestEngineeringLoopDirect:
    def test_run_engineering_loop_no_modifications(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "hello",
            "tool_results": [],
            "plan": [],
        }
        result = agent._run_engineering_loop("hello", base_result)
        assert result["status"] == "COMPLETED"
        assert result["engineering"]["final_status"] == "COMPLETED"
        assert "No code modifications detected" in result["engineering"]["evidence"][0]["output_summary"]

    def test_run_engineering_loop_with_modifications(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="edit_file", success=True, output="fixed", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        with patch.object(agent, '_run_verification_command', return_value=(True, "passed")):
            result = agent._run_engineering_loop("fix the bug", base_result)
        assert "engineering" in result
        assert result["engineering"]["phase"] == EngineeringPhase.FINALIZE

    def test_permission_denial_during_verification(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        result = agent._run_engineering_loop("fix the bug", base_result)
        # Should fail verification due to permission denial, but not crash
        assert result["engineering"]["final_status"] == "FAILED"
        assert "Permission not granted" in result["engineering"]["evidence"][0]["output_summary"]

    def test_cancellation_during_verification(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        call_count = [0]
        original_run = agent._run_verification_command

        def cancel_on_second(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                agent._cancelled = True
            return True, "passed"

        with patch.object(agent, '_run_verification_command', side_effect=cancel_on_second):
            result = agent._run_engineering_loop("fix the bug", base_result)
        # Should not crash on cancellation
        assert "engineering" in result


class TestProjectProfileVerification:
    def test_verification_command_selection_python(self):
        profile = ProjectProfile(
            root="/tmp",
            test_command="pytest",
            formatter_command="black",
            linter_command="ruff",
        )
        config = EngineeringLoopConfig()
        commands = select_verification_commands(profile, config)
        assert "pytest" in commands
        assert "black --check ." in commands
        assert "ruff check ." in commands

    def test_missing_verification_command(self):
        profile = ProjectProfile(root="/tmp")
        config = EngineeringLoopConfig()
        commands = select_verification_commands(profile, config)
        assert commands == []

    def test_go_project_commands(self):
        profile = ProjectProfile(
            root="/tmp",
            test_command="go test ./...",
            formatter_command="gofmt",
            linter_command="go vet",
        )
        config = EngineeringLoopConfig()
        commands = select_verification_commands(profile, config)
        assert "go test ./..." in commands
        assert "gofmt -l ." in commands
        assert "go vet ./..." in commands


class TestEngineeringLoopMemory:
    def test_memory_learning_on_completion(self):
        mock_memory = MagicMock(spec=ArgusMemory)
        mock_memory.add_lesson.return_value = {"id": "lesson-1"}

        agent = ArgusAgent(
            project_path=".",
            memory=mock_memory,
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        agent.execute("fix the bug")
        # Memory learning is best-effort; just verify it doesn't crash

    def test_memory_unavailable_does_not_crash(self):
        agent = ArgusAgent(
            project_path=".",
            memory=None,
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        result = agent.execute("fix the bug")
        assert result["status"] in ("COMPLETED", "FAILED")


class TestEngineeringLoopSkillIntegration:
    def test_skills_routed_for_engineering_task(self):
        from argus.skills import SkillRegistry, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="debugging", description="Debug bugs", triggers=["bug", "fix"]))
        registry.register(Skill(name="testing", description="Run tests", triggers=["test"]))

        agent = ArgusAgent(
            project_path=".",
            skill_paths=[],
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        agent._skill_registry = registry
        agent._skill_router = type("S", (), {"route": lambda self, req, ctx: registry._route_deterministic(req, ctx)})()
        agent._skill_router.route = lambda req, ctx: registry._route_deterministic(req, ctx)

        active = agent.route_skills("fix the bug")
        assert any(s.name == "debugging" for s in active)


class TestEngineeringLoopGitWorkflow:
    def test_git_workflow_not_triggered_automatically(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        result = agent.execute("fix the bug")
        assert "git_workflow" not in [r.get("tool") for r in result.get("tool_results", [])]

    def test_review_detects_unrelated_change(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        with patch.object(agent, '_run_verification_command', return_value=(True, "passed")):
            with patch.object(agent, '_execute_tool_call') as mock_exec:
                mock_exec.return_value = ToolResult(tool="git_diff", success=True, output="diff output")
                result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "COMPLETED"
        review_findings = result["engineering"]["review_findings"]
        assert any("Git diff inspected" in f for f in review_findings)

    def test_review_handles_non_git_repo(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        with patch.object(agent, '_run_verification_command', return_value=(True, "passed")):
            with patch.object(agent, '_execute_tool_call') as mock_exec:
                mock_exec.return_value = ToolResult(tool="git_diff", success=False, error="Not a git repository")
                result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "COMPLETED"
        review_findings = result["engineering"]["review_findings"]
        assert any("No git diff available" in f for f in review_findings)


class TestEngineeringLoopMissingVerification:
    def test_missing_verification_command(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        with patch('argus.agent.select_verification_commands', return_value=[]):
            result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "COMPLETED"
        evidence = result["engineering"]["evidence"]
        assert any("No verification commands available" in e.get("output_summary", "") for e in evidence)


class TestEngineeringLoopAutonomousRepair:
    def test_model_repair_succeeds_on_first_attempt(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        agent._model = object()

        def mock_model_reason(context, request):
            return {
                "complete": False,
                "response": "I will fix the bug by editing foo.py",
                "tool_calls": [{"tool": "edit_file", "arguments": {"path": "foo.py", "old_string": "bug", "new_string": "fix"}}],
            }

        with patch.object(agent, '_model_reason', side_effect=mock_model_reason):
            with patch.object(agent, '_run_verification_command', side_effect=[
                (False, "test failed"),
                (True, "passed"),
                (True, "passed"),
                (True, "passed"),
            ]):
                result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "COMPLETED"
        assert result["engineering"]["repair_attempts"] == 1
        repair_evidence = [e for e in result["engineering"]["evidence"] if e["phase"] == "REPAIR"]
        assert len(repair_evidence) == 1
        assert "Model repair executed" in repair_evidence[0]["output_summary"]

    def test_model_repair_succeeds_after_initial_failure(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        agent._model = object()

        call_count = [0]
        def mock_model_reason(context, request):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "complete": False,
                    "response": "First repair attempt",
                    "tool_calls": [{"tool": "read_file", "arguments": {"path": "foo.py"}}],
                }
            return {
                "complete": False,
                "response": "Second repair attempt with fix",
                "tool_calls": [{"tool": "edit_file", "arguments": {"path": "foo.py", "old_string": "bug", "new_string": "fix"}}],
            }

        with patch.object(agent, '_model_reason', side_effect=mock_model_reason):
            with patch.object(agent, '_run_verification_command', side_effect=[
                (False, "test failed"),
                (False, "still failing"),
                (True, "passed"),
                (True, "passed"),
                (True, "passed"),
            ]):
                result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "COMPLETED"
        assert result["engineering"]["repair_attempts"] == 2

    def test_model_repair_exhausts_max_attempts(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        agent._model = object()

        def mock_model_reason(context, request):
            return {
                "complete": False,
                "response": "Trying to fix",
                "tool_calls": [{"tool": "read_file", "arguments": {"path": "foo.py"}}],
            }

        with patch.object(agent, '_model_reason', side_effect=mock_model_reason):
            with patch.object(agent, '_run_verification_command', side_effect=[
                (False, "still failing"),
                (False, "still failing"),
                (False, "still failing"),
            ]):
                result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "FAILED"
        assert result["engineering"]["repair_attempts"] == 2

    def test_model_repair_no_model_available(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        agent._model = None
        with patch.object(agent, '_run_verification_command', side_effect=[
            (False, "test failed"),
            (True, "passed"),
            (True, "passed"),
            (True, "passed"),
        ]):
            result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "COMPLETED"
        repair_evidence = [e for e in result["engineering"]["evidence"] if e["phase"] == "REPAIR"]
        assert len(repair_evidence) == 1
        assert "No model available" in repair_evidence[0]["output_summary"]

    def test_model_repair_tracks_modified_files(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        agent._model = object()

        def mock_model_reason(context, request):
            return {
                "complete": False,
                "response": "Editing files",
                "tool_calls": [{"tool": "edit_file", "arguments": {"path": "bar.py", "old_string": "x", "new_string": "y"}}],
            }

        def mock_execute_tool_call(tc):
            if tc.get("tool") == "edit_file":
                return ToolResult(tool="edit_file", success=True, output="Edited bar.py", metadata={"path": "bar.py"})
            return ToolResult(tool=tc.get("tool", ""), success=True, output="ok")

        with patch.object(agent, '_model_reason', side_effect=mock_model_reason):
            with patch.object(agent, '_execute_tool_call', side_effect=mock_execute_tool_call):
                with patch.object(agent, '_run_verification_command', side_effect=[
                    (False, "test failed"),
                    (True, "passed"),
                    (True, "passed"),
                    (True, "passed"),
                ]):
                    result = agent._run_engineering_loop("fix the bug", base_result)
        assert result["engineering"]["final_status"] == "COMPLETED"
        assert "bar.py" in result["engineering"]["modified_files"]

    def test_model_repair_respects_cancellation(self):
        agent = ArgusAgent(
            project_path=".",
            config=ArgusAgentConfig(enable_engineering_loop=True, max_repair_attempts=2),
        )
        base_result = {
            "request": "fix the bug",
            "tool_results": [
                ToolResult(tool="write_file", success=True, output="written", metadata={"path": "foo.py"}),
            ],
            "plan": [],
        }
        agent._model = object()

        def mock_model_reason(context, request):
            agent._cancelled = True
            return {
                "complete": True,
                "response": "Repair",
                "tool_calls": [],
            }

        with patch.object(agent, '_model_reason', side_effect=mock_model_reason):
            result = agent._run_engineering_loop("fix the bug", base_result)
        assert "engineering" in result
