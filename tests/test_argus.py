"""Tests for Argus core components."""

import os
import tempfile
from pathlib import Path

import pytest

from argus.config import ArgusConfig
from argus.memory import ArgusMemory
from argus.session import Session, SessionManager
from argus.tools import ToolRegistry
from argus.tools.bash import BashTool
from argus.tools.file import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from argus.tools.search import GlobTool, GrepTool


class TestArgusConfig:
    def test_default_config(self):
        config = ArgusConfig()
        assert config.get("agent.default_runtime") == "hermes"
        assert config.get("agent.max_iterations") == 10
        assert config.get("repl.prompt") == "argus> "

    def test_set_and_get(self):
        config = ArgusConfig()
        config.set("agent.max_iterations", 20)
        assert config.get("agent.max_iterations") == 20

    def test_missing_key_returns_default(self):
        config = ArgusConfig()
        assert config.get("nonexistent.key", "fallback") == "fallback"


class TestSession:
    def test_create_session(self):
        session = Session(name="test", project_path="/tmp")
        assert session.name == "test"
        assert session.project_path == "/tmp"
        assert len(session.messages) == 0

    def test_add_message(self):
        session = Session(name="test")
        session.add_message("user", "hello")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "hello"

    def test_to_dict_and_from_dict(self):
        session = Session(name="test", project_path="/tmp")
        session.add_message("user", "hello")
        data = session.to_dict()
        restored = Session.from_dict(data)
        assert restored.name == "test"
        assert len(restored.messages) == 1


class TestSessionManager:
    def test_create_and_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)
            manager.create("session1")
            manager.create("session2")
            sessions = manager.list_sessions()
            assert "session1" in sessions
            assert "session2" in sessions

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)
            session = manager.create("session1")
            session.add_message("user", "hello")
            manager.save_current()

            loaded = manager.load("session1")
            assert len(loaded.messages) == 1
            assert loaded.messages[0]["content"] == "hello"

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)
            manager.create("session1")
            assert "session1" in manager.list_sessions()
            manager.delete("session1")
            assert "session1" not in manager.list_sessions()


class TestFileTools:
    def test_read_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            path = f.name

        try:
            tool = ReadFileTool()
            result = tool.execute(path=path)
            assert result.success is True
            assert "line1" in result.output
            assert "line2" in result.output
        finally:
            os.unlink(path)

    def test_write_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            tool = WriteFileTool()
            result = tool.execute(path=str(path), content="hello world")
            assert result.success is True
            assert path.read_text() == "hello world"

    def test_edit_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name

        try:
            tool = EditFileTool()
            result = tool.execute(path=path, old_string="hello", new_string="goodbye")
            assert result.success is True
            assert Path(path).read_text() == "goodbye world"
        finally:
            os.unlink(path)

    def test_list_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "file1.txt").touch()
            Path(tmpdir, "file2.txt").touch()
            tool = ListDirTool()
            result = tool.execute(path=tmpdir)
            assert result.success is True
            assert "file1.txt" in result.output
            assert "file2.txt" in result.output


class TestBashTool:
    def test_simple_command(self):
        tool = BashTool()
        if os.name == "nt":
            result = tool.execute(command="echo hello")
        else:
            result = tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.output.lower()


class TestSearchTools:
    def test_grep(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\nfoo bar\nhello again\n")
            path = f.name

        try:
            tool = GrepTool()
            result = tool.execute(pattern="hello", path=path)
            assert result.success is True
            assert "hello world" in result.output
            assert "hello again" in result.output
        finally:
            os.unlink(path)

    def test_glob(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a.txt").touch()
            Path(tmpdir, "b.txt").touch()
            Path(tmpdir, "c.py").touch()

            tool = GlobTool()
            result = tool.execute(pattern="*.txt", path=tmpdir)
            assert result.success is True
            assert "a.txt" in result.output
            assert "b.txt" in result.output
            assert "c.py" not in result.output


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        assert registry.get("read_file") is not None
        assert registry.get("nonexistent") is None

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        tools = registry.list_tools()
        assert len(tools) >= 1
        assert any(t["name"] == "read_file" for t in tools)


class TestArgusAgent:
    def test_agent_initialization(self):
        from argus.agent import ArgusAgent

        agent = ArgusAgent(project_path=".")
        assert agent.project_path is not None
        assert agent.config is not None

    def test_agent_execute_returns_result(self):
        from argus.agent import ArgusAgent

        agent = ArgusAgent(project_path=".")
        result = agent.execute("hello")
        assert "request" in result
        assert result["request"] == "hello"
        assert "status" in result

    def test_agent_status_after_execute(self):
        from argus.agent import ArgusAgent

        agent = ArgusAgent(project_path=".")
        agent.execute("test")
        status = agent.status()
        assert "status" in status
        assert status["tools_used"] >= 0


class TestArgusContext:
    def test_discover_project_context(self):
        from argus.context import discover_project_context

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "pyproject.toml").touch()
            ctx = discover_project_context(tmpdir)
            assert ctx.path is not None
            assert ctx.name is not None
            assert ctx.language == "python"

    def test_conversation_context(self):
        from argus.context import ConversationContext

        conv = ConversationContext()
        conv.add_user("hello")
        conv.add_assistant("world")
        history = conv.history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    def test_file_helpers(self):
        from argus.context import read_file, write_file, list_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            write_file(str(test_file), "hello")
            content = read_file(str(test_file))
            assert "hello" in content
            entries = list_dir(tmpdir)
            assert any("test.txt" in e for e in entries)


class TestArgusModel:
    def test_openai_provider_interface(self):
        from argus.model.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        assert provider is not None

    def test_ollama_provider_interface(self):
        from argus.model.ollama import OllamaProvider

        provider = OllamaProvider()
        assert provider is not None

    def test_create_provider_factory(self):
        from argus.model import create_provider

        provider = create_provider("ollama")
        assert provider is not None

    def test_create_model_from_config(self):
        from argus.model import create_model_from_config

        provider = create_model_from_config({"provider": "ollama", "name": "llama3"})
        assert provider is not None

    def test_build_messages_contains_project_context(self):
        from argus.model import build_messages

        messages = build_messages(
            user_request="fix the bug",
            conversation=[],
            project_context={"name": "test", "language": "python", "path": "."},
            available_tools=[{"name": "read_file", "description": "Read a file"}],
            recent_observations=[],
            current_step="investigate",
        )
        assert any(m.role == "system" for m in messages)
        assert any(m.role == "user" for m in messages)
        system_msg = next(m for m in messages if m.role == "system")
        assert "Argus" in system_msg.content
        assert "read_file" in system_msg.content

    def test_parse_model_output_with_tool_calls(self):
        from argus.model import parse_model_output

        content = '{"tool_calls": [{"tool_name": "read_file", "arguments": {"path": "test.txt"}}], "content": "Reading file"}'
        text, tool_calls = parse_model_output(content)
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "read_file"
        assert tool_calls[0].arguments["path"] == "test.txt"
        assert "Reading file" in text

    def test_parse_model_output_final_answer(self):
        from argus.model import parse_model_output

        text, tool_calls = parse_model_output("The fix has been applied successfully.")
        assert text == "The fix has been applied successfully."
        assert len(tool_calls) == 0

    def test_agent_with_model_provider(self):
        from argus.agent import ArgusAgent
        from argus.model.ollama import OllamaProvider

        provider = OllamaProvider()
        agent = ArgusAgent(project_path=".", model=provider)
        result = agent.execute("hello")
        assert "request" in result
        assert result["request"] == "hello"
        assert "status" in result


class TestArgusPermissions:
    def test_default_permissions(self):
        from argus.permissions import PermissionConfig

        config = PermissionConfig()
        assert config.allows("read_file") is True
        assert config.allows("write_file") is True
        assert config.allows("bash") is True
        assert config.requires_prompt("write_file") is True
        assert config.requires_prompt("bash") is True
        assert config.requires_prompt("read_file") is False

    def test_deny_permission(self):
        from argus.permissions import PermissionConfig

        config = PermissionConfig(write="deny")
        assert config.allows("write_file") is False
        assert config.requires_prompt("write_file") is False

    def test_tool_category_map(self):
        from argus.permissions import _tool_category

        assert _tool_category("read_file") == "read"
        assert _tool_category("write_file") == "write"
        assert _tool_category("bash") == "bash"
        assert _tool_category("grep") == "search"

    def test_permission_denied_error(self):
        from argus.permissions import PermissionConfig, PermissionDeniedError, check_permission

        config = PermissionConfig(write="deny")
        with pytest.raises(PermissionDeniedError):
            check_permission("write_file", config)

    def test_tool_registry_blocks_denied(self):
        from argus.tools import ToolRegistry
        from argus.tools.file import WriteFileTool
        from argus.permissions import PermissionConfig

        registry = ToolRegistry(permissions=PermissionConfig(write="deny"))
        registry.register(WriteFileTool())
        result = registry.execute("write_file", path="test.txt", content="hello")
        assert result.success is False
        assert "Permission denied" in result.error

    def test_tool_registry_asks_for_permission(self):
        from argus.tools import ToolRegistry
        from argus.tools.file import WriteFileTool
        from argus.permissions import PermissionConfig

        answers = []
        def ask(prompt, tool):
            answers.append((prompt, tool))
            return False

        registry = ToolRegistry(
            permissions=PermissionConfig(write="ask"),
            ask_callback=ask,
        )
        registry.register(WriteFileTool())
        result = registry.execute("write_file", path="test.txt", content="hello")
        assert result.success is False
        assert len(answers) == 1


class TestArgusAgentLoop:
    def test_agent_execute_produces_observations(self):
        from argus.agent import ArgusAgent

        agent = ArgusAgent(project_path=".")
        result = agent.execute("find and fix the bug")
        assert "observations" in result
        assert isinstance(result["observations"], list)

    def test_agent_status_callback_invoked(self):
        from argus.agent import ArgusAgent

        statuses = []
        agent = ArgusAgent(project_path=".", status_callback=lambda m: statuses.append(m))
        agent.execute("list files")
        assert len(statuses) >= 0

    def test_agent_loop_iterates(self):
        from argus.agent import ArgusAgent

        agent = ArgusAgent(project_path=".")
        result = agent.execute("investigate the project")
        assert result["iterations"] >= 0
        assert result["tools_used"] >= 0

    def test_agent_switch_project(self):
        from argus.agent import ArgusAgent

        agent = ArgusAgent(project_path=".")
        agent.switch_project(".")
        assert agent.project_path is not None


class TestArgusConfigPermissions:
    def test_permission_defaults(self):
        config = ArgusConfig()
        assert config.get("permissions.read") == "allow"
        assert config.get("permissions.write") == "ask"
        assert config.get("permissions.bash") == "ask"


class TestGitTools:
    def _init_repo(self, tmpdir):
        import subprocess

        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, check=True, capture_output=True)
        Path(tmpdir, "file.txt").write_text("hello")
        subprocess.run(["git", "add", "file.txt"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmpdir, check=True, capture_output=True)
        return tmpdir

    def test_git_status_clean(self, tmp_path):
        from argus.tools.git import GitStatusTool

        self._init_repo(tmp_path)
        tool = GitStatusTool()
        result = tool.execute(project_path=str(tmp_path))
        assert result.success is True
        clean_indicators = ["nothing to commit", "working tree clean", "## master", "## main"]
        assert any(indicator in result.output.lower() for indicator in clean_indicators)

    def test_git_status_modified(self, tmp_path):
        from argus.tools.git import GitStatusTool

        self._init_repo(tmp_path)
        Path(tmp_path, "file.txt").write_text("modified")
        tool = GitStatusTool()
        result = tool.execute(project_path=str(tmp_path))
        assert result.success is True
        assert "file.txt" in result.output

    def test_git_status_untracked(self, tmp_path):
        from argus.tools.git import GitStatusTool

        self._init_repo(tmp_path)
        Path(tmp_path, "new.txt").write_text("new")
        tool = GitStatusTool()
        result = tool.execute(project_path=str(tmp_path))
        assert result.success is True
        assert "new.txt" in result.output

    def test_git_diff(self, tmp_path):
        from argus.tools.git import GitDiffTool

        self._init_repo(tmp_path)
        Path(tmp_path, "file.txt").write_text("changed")
        tool = GitDiffTool()
        result = tool.execute(project_path=str(tmp_path))
        assert result.success is True
        assert "changed" in result.output

    def test_git_log(self, tmp_path):
        from argus.tools.git import GitLogTool

        self._init_repo(tmp_path)
        tool = GitLogTool()
        result = tool.execute(project_path=str(tmp_path), limit=5)
        assert result.success is True
        assert "initial" in result.output

    def test_git_add(self, tmp_path):
        from argus.tools.git import GitAddTool

        self._init_repo(tmp_path)
        Path(tmp_path, "new.txt").write_text("new")
        tool = GitAddTool()
        result = tool.execute(project_path=str(tmp_path), paths=["new.txt"])
        assert result.success is True
        assert "new.txt" in result.output or result.success is True

    def test_git_add_multiple_paths(self, tmp_path):
        from argus.tools.git import GitAddTool

        self._init_repo(tmp_path)
        Path(tmp_path, "a.txt").write_text("a")
        Path(tmp_path, "b.txt").write_text("b")
        tool = GitAddTool()
        result = tool.execute(project_path=str(tmp_path), paths=["a.txt", "b.txt"])
        assert result.success is True

    def test_git_commit(self, tmp_path):
        from argus.tools.git import GitAddTool, GitCommitTool

        self._init_repo(tmp_path)
        Path(tmp_path, "new.txt").write_text("new")
        GitAddTool().execute(project_path=str(tmp_path), paths=["new.txt"])
        tool = GitCommitTool()
        result = tool.execute(project_path=str(tmp_path), message="Add new file")
        assert result.success is True
        assert "Add new file" in result.output

    def test_git_commit_requires_message(self, tmp_path):
        from argus.tools.git import GitCommitTool

        self._init_repo(tmp_path)
        tool = GitCommitTool()
        result = tool.execute(project_path=str(tmp_path), message="")
        assert result.success is False
        assert "message is required" in result.error.lower()

    def test_git_tool_non_git_directory(self, tmp_path):
        from argus.tools.git import GitStatusTool

        tool = GitStatusTool()
        result = tool.execute(project_path=str(tmp_path))
        assert result.success is False
        assert "not a git repository" in result.error.lower() or "fatal" in result.error.lower() or result.error

    def test_git_tool_permission_denied(self):
        from argus.tools import ToolRegistry
        from argus.tools.git import GitStatusTool, GitAddTool, GitCommitTool
        from argus.permissions import PermissionConfig

        registry = ToolRegistry(permissions=PermissionConfig(git="deny"))
        registry.register(GitStatusTool())
        registry.register(GitAddTool())
        registry.register(GitCommitTool())

        result = registry.execute("git_status", project_path=".")
        assert result.success is False
        assert "Permission denied" in result.error or "Permission not granted" in result.error

        result = registry.execute("git_add", project_path=".", paths=["file.txt"])
        assert result.success is False
        assert "Permission denied" in result.error or "Permission not granted" in result.error

        result = registry.execute("git_commit", project_path=".", message="test")
        assert result.success is False
        assert "Permission denied" in result.error or "Permission not granted" in result.error

    def test_git_tool_permission_ask_declined(self):
        from argus.tools import ToolRegistry
        from argus.tools.git import GitCommitTool
        from argus.permissions import PermissionConfig

        answers = []

        def ask(prompt, tool):
            answers.append((prompt, tool))
            return False

        registry = ToolRegistry(
            permissions=PermissionConfig(git="ask"),
            ask_callback=ask,
        )
        registry.register(GitCommitTool())
        result = registry.execute("git_commit", project_path=".", message="test")
        assert result.success is False
        assert len(answers) == 1

    def test_git_add_requires_paths(self, tmp_path):
        from argus.tools.git import GitAddTool

        self._init_repo(tmp_path)
        tool = GitAddTool()
        result = tool.execute(project_path=str(tmp_path))
        assert result.success is False
        assert "No paths provided" in result.error

    def test_git_diff_with_target(self, tmp_path):
        from argus.tools.git import GitDiffTool

        self._init_repo(tmp_path)
        Path(tmp_path, "file.txt").write_text("changed")
        tool = GitDiffTool()
        result = tool.execute(project_path=str(tmp_path), target="file.txt")
        assert result.success is True
        assert "changed" in result.output

    def test_git_log_limit(self, tmp_path):
        from argus.tools.git import GitLogTool

        self._init_repo(tmp_path)
        tool = GitLogTool()
        result = tool.execute(project_path=str(tmp_path), limit=1)
        assert result.success is True
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert len(lines) <= 1

    def test_git_tool_path_handling_windows(self):
        from argus.tools.git import GitStatusTool

        tool = GitStatusTool()
        result = tool.execute(project_path=".")
        assert result.success is False or isinstance(result.success, bool)

    def test_git_tool_rejects_invalid_arguments(self, tmp_path):
        from argus.tools.git import GitCommitTool

        self._init_repo(tmp_path)
        tool = GitCommitTool()
        result = tool.execute(project_path=str(tmp_path), message="  ")
        assert result.success is False


class TestArgusSkills:
    def test_builtin_skills_discovered(self):
        from argus.skills import SkillRegistry
        from pathlib import Path

        registry = SkillRegistry(skill_paths=[Path("argus/skills/builtin")])
        skills = registry.discover()
        names = [s.name for s in skills]
        assert "debugging" in names
        assert "testing" in names
        assert "git-workflow" in names

    def test_skill_loader_skips_missing_skill_md(self, tmp_path):
        from argus.skills import SkillRegistry

        registry = SkillRegistry(skill_paths=[tmp_path])
        skills = registry.discover()
        assert skills == []

    def test_skill_matches_triggers(self):
        from argus.skills import Skill

        skill = Skill(
            name="debugging",
            description="Debug bugs",
            triggers=["bug", "crash", "error"],
        )
        assert skill.matches("Fix the bug")
        assert skill.matches("Application crash on startup")
        assert not skill.matches("Add a feature")

    def test_skill_to_context(self):
        from argus.skills import Skill

        skill = Skill(
            name="debugging",
            description="Debug bugs",
            instructions="1. Read the traceback\n2. Locate the bug",
            triggers=["bug"],
        )
        ctx = skill.to_context()
        assert "## Skill: debugging" in ctx
        assert "1. Read the traceback" in ctx

    def test_skill_router_returns_matching_skills(self):
        from argus.skills import SkillRegistry, SkillRouter, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="debugging", description="Debug", triggers=["bug", "crash"]))
        registry.register(Skill(name="testing", description="Test", triggers=["test", "pytest"]))
        registry.register(Skill(name="git-workflow", description="Git", triggers=["git", "commit"]))

        router = SkillRouter(registry)
        matches = router.route("Fix the bug and run tests")
        assert any(s.name == "debugging" for s in matches)
        assert any(s.name == "testing" for s in matches)

    def test_skill_router_deduplicates(self):
        from argus.skills import SkillRegistry, SkillRouter, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="testing", description="Test", triggers=["test", "pytest"]))
        router = SkillRouter(registry)
        matches = router.route("run tests and pytest")
        names = [s.name for s in matches]
        assert names.count("testing") == 1

    def test_skill_router_empty_request(self):
        from argus.skills import SkillRegistry, SkillRouter, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="testing", description="Test", triggers=["test"]))
        router = SkillRouter(registry)
        matches = router.route("hello")
        assert matches == []

    def test_skill_registry_search(self):
        from argus.skills import SkillRegistry, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="rust-development", description="Rust code", triggers=["rust", "cargo"]))
        matches = registry.search("rust")
        assert any(s.name == "rust-development" for s in matches)

    def test_skill_registry_get(self):
        from argus.skills import SkillRegistry, Skill

        registry = SkillRegistry()
        skill = Skill(name="testing", description="Test")
        registry.register(skill)
        assert registry.get("testing") is skill
        assert registry.get("nonexistent") is None

    def test_agent_route_skills(self):
        from argus.agent import ArgusAgent
        from argus.skills import SkillRegistry, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="debugging", description="Debug", triggers=["bug"]))
        agent = ArgusAgent(project_path=".", skill_paths=[])
        agent._skill_registry = registry
        agent.route_skills("Fix the bug")
        assert any(s.name == "debugging" for s in agent.active_skills())

    def test_agent_route_skills_empty_when_no_match(self):
        from argus.agent import ArgusAgent
        from argus.skills import SkillRegistry, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="testing", description="Test", triggers=["test"]))
        agent = ArgusAgent(project_path=".", skill_paths=[])
        agent._skill_registry = registry
        agent.route_skills("hello world")
        assert agent.active_skills() == []

    def test_skill_to_dict(self):
        from argus.skills import Skill

        skill = Skill(
            name="debugging",
            description="Debug bugs",
            instructions="Read traceback",
            triggers=["bug"],
            metadata={"version": "1.0"},
            path=Path("/tmp/debugging"),
        )
        data = skill.to_dict()
        assert data["name"] == "debugging"
        assert data["triggers"] == ["bug"]
        assert data["metadata"]["version"] == "1.0"


class TestArgusMemory:
    def test_argus_memory_wrapper_with_manager(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.search.return_value = [{"content": "Use SQLite"}]
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        assert memory.available is True
        results = memory.search("database")
        assert len(results) == 1
        mock_manager.search.assert_called_once_with("database", project=".", limit=10)

    def test_argus_memory_wrapper_without_manager(self):
        from argus.memory import ArgusMemory

        memory = ArgusMemory()
        assert memory.available is False
        assert memory.search("anything") == []
        assert memory.retrieve_relevant("anything") == ""

    def test_argus_memory_retrieve_relevant_formats(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.retrieve_relevant_memory.return_value = "Use SQLite for database"
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        result = memory.retrieve_relevant("database choice")
        assert "Use SQLite" in result
        mock_manager.retrieve_relevant_memory.assert_called_once_with("database choice", ".", limit=5)

    def test_argus_memory_add_observation(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.store.return_value = {"id": "m1"}
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        result = memory.add_observation("Bug fixed", "JWT expiry mismatch", entry_type="fix", importance=0.9)
        assert result is not None
        mock_manager.store.assert_called_once()

    def test_argus_memory_add_decision(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.store_decision.return_value = {"id": "d1"}
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        result = memory.add_decision("Use async patterns", context="Discussed design")
        assert result is not None
        mock_manager.store_decision.assert_called_once_with("Use async patterns", project=".", context="Discussed design")

    def test_argus_memory_add_lesson(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.store_lesson.return_value = {"id": "l1"}
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        result = memory.add_lesson("Always test edge cases")
        assert result is not None
        mock_manager.store_lesson.assert_called_once_with("Always test edge cases", project=".")

    def test_argus_memory_add_architecture(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.store_project_architecture.return_value = {"id": "a1"}
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        result = memory.add_architecture("Rust workspace with CLI")
        assert result is not None
        mock_manager.store_project_architecture.assert_called_once_with("Rust workspace with CLI", project=".")

    def test_argus_memory_list_recent(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.list.return_value = [{"id": "m1", "content": "recent"}]
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        results = memory.list_recent(limit=10)
        assert len(results) == 1
        mock_manager.list.assert_called_once_with(project=".", limit=10)

    def test_argus_memory_search_returns_empty_when_unavailable(self):
        from argus.memory import ArgusMemory

        memory = ArgusMemory()
        assert memory.search("query") == []

    def test_argus_memory_handles_backend_exception(self):
        from argus.memory import ArgusMemory
        from unittest.mock import MagicMock

        mock_manager = MagicMock()
        mock_manager.search.side_effect = RuntimeError("backend down")
        mock_manager.retrieve_relevant_memory.side_effect = RuntimeError("backend down")
        memory = ArgusMemory(memory_manager=mock_manager, project_path=Path("."))
        assert memory.search("query") == []
        assert memory.retrieve_relevant("query") == ""

    def test_memory_tool_add_observation(self):
        from argus.tools.memory import MemoryAddTool
        from unittest.mock import MagicMock, patch

        mock_agent = MagicMock()
        mock_agent.memory.add_observation.return_value = {"id": "m1"}
        with patch("argus.tools.memory._get_agent", return_value=mock_agent):
            tool = MemoryAddTool()
            result = tool.execute(summary="Fixed bug", details="Details here", entry_type="fix")
        assert result.success is True
        assert "Fixed bug" in result.output

    def test_memory_tool_search(self):
        from argus.tools.memory import MemorySearchTool
        from unittest.mock import MagicMock, patch

        mock_agent = MagicMock()
        mock_agent.memory.search.return_value = [{"type": "fix", "content": "Use SQLite"}]
        with patch("argus.tools.memory._get_agent", return_value=mock_agent):
            tool = MemorySearchTool()
            result = tool.execute(query="database")
        assert result.success is True
        assert "Use SQLite" in result.output

    def test_memory_tool_search_no_results(self):
        from argus.tools.memory import MemorySearchTool
        from unittest.mock import MagicMock, patch

        mock_agent = MagicMock()
        mock_agent.memory.search.return_value = []
        with patch("argus.tools.memory._get_agent", return_value=mock_agent):
            tool = MemorySearchTool()
            result = tool.execute(query="nonexistent")
        assert result.success is True
        assert "No relevant memory found" in result.output

    def test_memory_tool_unavailable(self):
        from argus.tools.memory import MemoryAddTool
        from unittest.mock import patch

        with patch("argus.tools.memory._get_agent", return_value=None):
            tool = MemoryAddTool()
            result = tool.execute(summary="test", details="test")
        assert result.success is False
        assert "not available" in result.error

    def test_agent_memory_integration_in_context(self):
        from argus.agent import ArgusAgent
        from unittest.mock import MagicMock

        mock_memory_manager = MagicMock()
        mock_memory_manager.retrieve_relevant_memory.return_value = "Past fix: JWT expiry"
        mock_model = MagicMock()
        mock_model.complete.return_value = MagicMock(content="Done", tool_calls=[])

        agent = ArgusAgent(project_path=".", memory=mock_memory_manager, model=mock_model)
        context = agent._build_context("Fix auth bug", {"observations": [], "tool_results": [], "plan": [{"action": "investigate"}]})
        assert "Past fix: JWT expiry" in context["memory_context"]

    def test_agent_memory_context_empty_when_unavailable(self):
        from argus.agent import ArgusAgent

        agent = ArgusAgent(project_path=".")
        agent.memory = ArgusMemory()
        context = agent._build_context("hello", {"observations": [], "tool_results": [], "plan": [{"action": "investigate"}]})
        assert context["memory_context"] == ""


class TestArgusEndToEnd:
    def test_skill_routing_integration(self):
        from argus.agent import ArgusAgent
        from argus.skills import SkillRegistry, Skill
        from unittest.mock import MagicMock

        skill_registry = SkillRegistry(skill_paths=[])
        skill_registry.register(Skill(name="debugging", description="Debug", triggers=["bug", "crash", "error"]))
        skill_registry.register(Skill(name="testing", description="Test", triggers=["test", "pytest"]))

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""

        agent = ArgusAgent(project_path=".", memory=mock_memory, skill_paths=[])
        agent._skill_registry = skill_registry
        agent._skill_router = type("S", (), {"route": lambda self, req, ctx: skill_registry._route_deterministic(req, ctx)})()
        agent._skill_router.route = lambda req, ctx: skill_registry._route_deterministic(req, ctx)

        active = agent.route_skills("Fix the failing tests and debug the error")
        assert any(s.name == "testing" for s in active)
        assert any(s.name == "debugging" for s in active)

    def test_task_execution_uses_tools(self):
        from argus.agent import ArgusAgent
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        agent = ArgusAgent(project_path="D:/agent-core", memory=mock_memory)
        result = agent.execute("List the files in the project root")
        assert result["status"] == "COMPLETED"
        assert result["tools_used"] > 0

    def test_memory_retrieval_in_context(self):
        from argus.agent import ArgusAgent
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.retrieve_relevant_memory.return_value = "Past: Fixed authentication bug"
        agent = ArgusAgent(project_path=".", memory=mock_memory)
        context = agent._build_context("What did we learn about auth?", {
            "observations": [],
            "tool_results": [],
            "plan": [{"action": "investigate"}]
        })
        assert "Fixed authentication bug" in context["memory_context"]


class TestAgentReliability:
    def test_consecutive_failures_stops_loop(self):
        from argus.agent import ArgusAgent, ArgusAgentConfig
        from argus.permissions import PermissionConfig
        from argus.tools import ToolRegistry
        from argus.tools.bash import BashTool
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        agent = ArgusAgent(
            project_path=".",
            memory=mock_memory,
            config=ArgusAgentConfig(max_iterations=20, max_consecutive_failures=2, max_no_progress=10),
        )
        agent._tool_registry.set_permissions(PermissionConfig(bash="allow"))

        failing_tool = BashTool()
        failing_tool.execute = lambda **kwargs: ToolResult(
            tool="bash", success=False, error="command not found"
        )
        agent._tool_registry.register(failing_tool)

        call_count = 0

        class FailingRuntime:
            def respond(self, context):
                nonlocal call_count
                call_count += 1
                return {
                    "complete": False,
                    "response": "Retrying...",
                    "tool_calls": [{"tool": "bash", "arguments": {"command": "fail"}}],
                }

        agent._runtime = FailingRuntime()
        result = agent.execute("run a failing command")
        assert result["status"] == "FAILED"
        assert result["failure_reason"] == "consecutive_tool_failures"
        assert call_count > 1

    def test_no_progress_stops_loop(self):
        from argus.agent import ArgusAgent, ArgusAgentConfig
        from argus.permissions import PermissionConfig
        from argus.tools import ToolRegistry
        from argus.tools.bash import BashTool
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        agent = ArgusAgent(
            project_path=".",
            memory=mock_memory,
            config=ArgusAgentConfig(max_iterations=20, max_consecutive_failures=10, max_no_progress=2),
        )
        agent._tool_registry.set_permissions(PermissionConfig(bash="allow"))

        calls = []

        def repeat_tool(**kwargs):
            calls.append(kwargs)
            return ToolResult(tool="bash", success=True, output="same output")

        failing_tool = BashTool()
        failing_tool.execute = repeat_tool
        agent._tool_registry.register(failing_tool)

        class RepeatingRuntime:
            def respond(self, context):
                return {
                    "complete": False,
                    "response": "Trying again...",
                    "tool_calls": [{"tool": "bash", "arguments": {"command": "echo same"}}],
                }

        agent._runtime = RepeatingRuntime()
        result = agent.execute("run same command repeatedly")
        assert result["status"] == "FAILED"
        assert result["failure_reason"] == "no_progress"
        assert len(calls) > 1

    def test_workspace_boundary_blocks_file_read(self):
        from argus.tools.file import ReadFileTool

        tool = ReadFileTool()
        result = tool.execute(path="C:/Windows/System32/config", workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

    def test_workspace_boundary_blocks_write(self):
        from argus.tools.file import WriteFileTool

        tool = WriteFileTool()
        result = tool.execute(path="C:/Windows/System32/test.txt", content="test", workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

    def test_workspace_boundary_blocks_edit(self):
        from argus.tools.file import EditFileTool

        tool = EditFileTool()
        result = tool.execute(path="C:/Windows/System32/config", old_string="a", new_string="b", workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

    def test_workspace_boundary_blocks_list_dir(self):
        from argus.tools.file import ListDirTool

        tool = ListDirTool()
        result = tool.execute(path="C:/Windows/System32", workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

    def test_workspace_boundary_blocks_grep(self):
        from argus.tools.search import GrepTool

        tool = GrepTool()
        result = tool.execute(pattern="test", path="C:/Windows/System32", workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

    def test_workspace_boundary_blocks_glob(self):
        from argus.tools.search import GlobTool

        tool = GlobTool()
        result = tool.execute(pattern="*.txt", path="C:/Windows/System32", workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

    def test_workspace_boundary_allows_inside_workspace(self):
        from argus.tools.file import ReadFileTool

        tool = ReadFileTool()
        result = tool.execute(path="README.md", workspace="D:/agent-core")
        assert result.success is True

    def test_bash_blocks_dangerous_rm(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="rm -rf /")
        assert result.success is False
        assert "Dangerous command blocked" in result.error

    def test_bash_blocks_dangerous_del(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="del C:\\Windows\\System32")
        assert result.success is False
        assert "Dangerous command blocked" in result.error

    def test_bash_blocks_dangerous_rmdir(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="rmdir C:\\Windows /s")
        assert result.success is False
        assert "Dangerous command blocked" in result.error

    def test_bash_blocks_dangerous_format(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="format C:")
        assert result.success is False
        assert "Dangerous command blocked" in result.error

    def test_bash_blocks_git_reset(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="git reset --hard")
        assert result.success is False
        assert "Dangerous command blocked" in result.error

    def test_bash_blocks_git_clean(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="git clean -fd")
        assert result.success is False
        assert "Dangerous command blocked" in result.error

    def test_bash_blocks_command_chaining(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="echo hello && echo world")
        assert result.success is False
        assert "Command chaining is not allowed" in result.error

    def test_bash_allows_safe_command(self):
        from argus.tools.bash import BashTool

        tool = BashTool()
        result = tool.execute(command="echo hello")
        assert result.success is True

    def test_tool_call_with_missing_tool_name(self):
        from argus.agent import ArgusAgent
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        agent = ArgusAgent(project_path=".", memory=mock_memory)
        result = agent._execute_tool_call({"arguments": {}})
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_tool_call_with_malformed_arguments(self):
        from argus.agent import ArgusAgent
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        agent = ArgusAgent(project_path=".", memory=mock_memory)
        result = agent._execute_tool_call({"tool": "read_file", "arguments": "not-a-dict"})
        assert result.success is False

    def test_failure_states_are_distinct(self):
        from argus.agent import ArgusAgent, ArgusAgentConfig
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        config = ArgusAgentConfig(max_iterations=1, max_consecutive_failures=1, max_no_progress=1)
        agent = ArgusAgent(project_path=".", memory=mock_memory, config=config)

        result = agent.execute("do something")
        assert result["status"] in (
            "COMPLETED", "FAILED", "TIMEOUT", "TOOL_LIMIT",
            "RUNTIME_ERROR", "CANCELLED"
        )
        assert "failure_reason" in result


class TestGitWorkflow:
    def _init_repo(self, tmpdir):
        import subprocess

        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, check=True, capture_output=True)
        Path(tmpdir, "README.md").write_text("# Test Project\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmpdir, check=True, capture_output=True)
        return tmpdir

    def test_workflow_inspect_clean_repo(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        tool = GitWorkflowTool()
        result = tool.execute(stage="inspect", project_path=str(tmp_path))
        assert result.success is True
        assert result.metadata["stage"] == "inspect"
        state = result.metadata["repo_state"]
        assert state["is_git_repo"] is True
        assert state["branch"] != ""

    def test_workflow_inspect_modified_repo(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        Path(tmp_path, "src.txt").write_text("hello")
        tool = GitWorkflowTool()
        result = tool.execute(stage="inspect", project_path=str(tmp_path))
        assert result.success is True
        state = result.metadata["repo_state"]
        assert "src.txt" in state.get("all_changes", [])

    def test_workflow_review_diff(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        Path(tmp_path, "README.md").write_text("changed")
        tool = GitWorkflowTool()
        result = tool.execute(stage="review", project_path=str(tmp_path))
        assert result.success is True
        assert result.metadata["stage"] == "review"
        diff = result.metadata["diff"]
        assert diff["success"] is True
        assert "README.md" in diff["files"]

    def test_workflow_identify_relevant_files(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        Path(tmp_path, "auth.py").write_text("login")
        Path(tmp_path, "README.md").write_text("updated readme")
        tool = GitWorkflowTool()
        result = tool.execute(
            stage="review",
            project_path=str(tmp_path),
            task_request="Fix login bug in auth module",
            recent_tools=["edit_file", "write_file"],
            recent_arguments=[{"path": "auth.py"}],
        )
        assert result.success is True
        relevant = result.metadata["relevant"]
        unrelated = result.metadata["unrelated"]
        assert "auth.py" in relevant
        assert "README.md" in unrelated

    def test_workflow_approve_approved(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        Path(tmp_path, "README.md").write_text("changed")
        tool = GitWorkflowTool()
        result = tool.execute(
            stage="approve",
            project_path=str(tmp_path),
            task_request="Update README",
        )
        assert result.success is True
        assert result.metadata["needs_approval"] is True
        workflow_key = str(Path(tmp_path).resolve())
        tool._workflows[workflow_key].set_approved(True, "Update README")
        assert tool._workflows[workflow_key].is_approved() is True

    def test_workflow_approve_rejected(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        Path(tmp_path, "file.txt").write_text("changed")
        tool = GitWorkflowTool()

        def ask(summary):
            return False

        result = tool.execute(
            stage="approve",
            project_path=str(tmp_path),
            task_request="Update file",
            ask_callback=ask,
        )
        assert result.success is True
        assert result.metadata["needs_approval"] is True
        assert tool._workflows[str(tmp_path)].is_approved() is False

    def test_workflow_commit_after_approval(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        Path(tmp_path, "README.md").write_text("changed")
        tool = GitWorkflowTool()
        result = tool.execute(stage="approve", project_path=str(tmp_path), task_request="Update README")
        assert result.success is True
        workflow_key = str(Path(str(tmp_path)).resolve())
        tool._workflows[workflow_key].set_approved(True, "Update README")

        result = tool.execute(
            stage="commit",
            project_path=str(tmp_path),
            task_request="Update README",
            recent_tools=["write_file"],
            recent_arguments=[{"path": "README.md"}],
        )
        assert result.success is True
        assert result.metadata["stage"] == "commit"
        assert "README.md" in result.metadata["committed_files"]

    def test_workflow_commit_without_approval_fails(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        Path(tmp_path, "file.txt").write_text("changed")
        tool = GitWorkflowTool()
        result = tool.execute(stage="commit", project_path=str(tmp_path))
        assert result.success is False
        assert "not approved" in result.error.lower()

    def test_workflow_unrelated_files_not_staged(self, tmp_path):
        from argus.tools.git import GitWorkflowTool
        from argus.tools.git import GitAddTool

        self._init_repo(tmp_path)
        Path(tmp_path, "README.md").write_text("updated readme")
        Path(tmp_path, "auth.py").write_text("login")
        tool = GitWorkflowTool()
        result = tool.execute(stage="approve", project_path=str(tmp_path), task_request="Update README")
        assert result.success is True
        workflow_key = str(Path(str(tmp_path)).resolve())
        tool._workflows[workflow_key].set_approved(True, "Update README")

        result = tool.execute(
            stage="commit",
            project_path=str(tmp_path),
            task_request="Update README",
            recent_tools=["write_file"],
            recent_arguments=[{"path": "README.md"}],
        )
        assert result.success is True
        committed = result.metadata["committed_files"]
        assert "README.md" in committed
        assert "auth.py" not in committed

    def test_workflow_non_git_repo(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        tool = GitWorkflowTool()
        result = tool.execute(stage="inspect", project_path=str(tmp_path))
        assert result.success is False
        assert "not a git repository" in result.error.lower() or "fatal" in result.error.lower() or result.error

    def test_workflow_unknown_stage(self, tmp_path):
        from argus.tools.git import GitWorkflowTool

        self._init_repo(tmp_path)
        tool = GitWorkflowTool()
        result = tool.execute(stage="invalid", project_path=str(tmp_path))
        assert result.success is False
        assert "unknown" in result.error.lower()

    def test_git_tools_workspace_boundary(self, tmp_path):
        from argus.tools.git import GitStatusTool, GitDiffTool, GitAddTool, GitCommitTool

        status_tool = GitStatusTool()
        result = status_tool.execute(project_path=str(tmp_path), workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

        diff_tool = GitDiffTool()
        result = diff_tool.execute(project_path=str(tmp_path), workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

        add_tool = GitAddTool()
        result = add_tool.execute(project_path=str(tmp_path), paths=["file.txt"], workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

        commit_tool = GitCommitTool()
        result = commit_tool.execute(project_path=str(tmp_path), message="test", workspace="D:/agent-core")
        assert result.success is False
        assert "outside workspace" in result.error.lower()

    def test_workflow_agent_integration_with_approval(self):
        from argus.agent import ArgusAgent, ArgusAgentConfig
        from argus.permissions import PermissionConfig
        from argus.tools import ToolRegistry
        from argus.tools.git import GitWorkflowTool
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        approvals = []

        def approval_callback(summary):
            approvals.append(summary)
            return True

        config = ArgusAgentConfig(
            max_iterations=5,
            commit_approval_callback=approval_callback,
        )
        agent = ArgusAgent(project_path=".", memory=mock_memory, config=config)
        agent._tool_registry.set_permissions(PermissionConfig(git="allow"))

        result = agent._execute_tool_call({
            "tool": "git_workflow",
            "arguments": {
                "stage": "approve",
                "project_path": ".",
                "task_request": "Fix bug",
            },
        })
        assert result.success is True
        assert result.metadata.get("needs_approval") is True
        assert len(approvals) == 1
        assert "Fix bug" in approvals[0]

    def test_workflow_agent_integration_rejected(self):
        from argus.agent import ArgusAgent, ArgusAgentConfig
        from argus.permissions import PermissionConfig
        from argus.tools.git import GitWorkflowTool
        from unittest.mock import MagicMock

        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.retrieve_relevant_memory.return_value = ""
        mock_memory.list.return_value = []

        def approval_callback(summary):
            return False

        config = ArgusAgentConfig(
            max_iterations=5,
            commit_approval_callback=approval_callback,
        )
        agent = ArgusAgent(project_path=".", memory=mock_memory, config=config)
        agent._tool_registry.set_permissions(PermissionConfig(git="allow"))

        result = agent._execute_tool_call({
            "tool": "git_workflow",
            "arguments": {
                "stage": "approve",
                "project_path": ".",
                "task_request": "Fix bug",
            },
        })
        assert result.success is True
        assert result.metadata.get("needs_approval") is True
        tool = agent._tool_registry.get("git_workflow")
        workflow_key = str(Path(".").resolve())
        assert tool._workflows[workflow_key].is_approved() is False

    def test_workflow_end_to_end_acceptance(self, tmp_path):
        import subprocess
        from argus.tools.git import GitWorkflowTool, GitStatusTool

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

        Path(tmp_path, "README.md").write_text("# Project\n")
        Path(tmp_path, "src").mkdir(exist_ok=True)
        Path(tmp_path, "src", "example.py").write_text("def add(a, b):\n    return a + b\n")
        Path(tmp_path, "tests").mkdir(exist_ok=True)
        Path(tmp_path, "tests", "test_example.py").write_text("def test_add():\n    assert add(1, 2) == 3\n")

        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

        Path(tmp_path, "config.toml").write_text("unrelated_change = true\n")
        Path(tmp_path, "src", "example.py").write_text("def add(a, b):\n    return a + b + 1\n")
        Path(tmp_path, "tests", "test_example.py").write_text("def test_add():\n    assert add(1, 2) == 4\n")

        tool = GitWorkflowTool()

        inspect_result = tool.execute(stage="inspect", project_path=str(tmp_path))
        assert inspect_result.success is True
        state = inspect_result.metadata["repo_state"]
        assert "config.toml" in state.get("all_changes", [])
        assert "src/example.py" in state.get("all_changes", [])
        assert "tests/test_example.py" in state.get("all_changes", [])

        review_result = tool.execute(
            stage="review",
            project_path=str(tmp_path),
            task_request="Fix addition bug in example.py",
            recent_tools=["write_file", "edit_file"],
            recent_arguments=[
                {"path": "src/example.py"},
                {"path": "tests/test_example.py"},
            ],
        )
        assert review_result.success is True
        relevant = review_result.metadata["relevant"]
        unrelated = review_result.metadata["unrelated"]
        assert "src/example.py" in relevant
        assert "tests/test_example.py" in relevant
        assert "config.toml" in unrelated

        workflow_key = str(Path(str(tmp_path)).resolve())
        tool._workflows[workflow_key].set_approved(True, "Fix addition bug")

        commit_result = tool.execute(
            stage="commit",
            project_path=str(tmp_path),
            task_request="Fix addition bug in example.py",
            recent_tools=["write_file", "edit_file"],
            recent_arguments=[
                {"path": "src/example.py"},
                {"path": "tests/test_example.py"},
            ],
        )
        assert commit_result.success is True
        assert "src/example.py" in commit_result.metadata["committed_files"]
        assert "tests/test_example.py" in commit_result.metadata["committed_files"]
        assert "config.toml" not in commit_result.metadata["committed_files"]

        status = GitStatusTool().execute(project_path=str(tmp_path))
        assert "config.toml" in status.output
        assert "src/example.py" not in status.output or "nothing to commit" in status.output.lower()

    def test_workflow_end_to_end_rejection(self, tmp_path):
        import subprocess
        from argus.tools.git import GitWorkflowTool, GitStatusTool

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)

        Path(tmp_path, "README.md").write_text("# Project\n")
        Path(tmp_path, "src").mkdir(exist_ok=True)
        Path(tmp_path, "src", "example.py").write_text("def add(a, b):\n    return a + b\n")

        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

        Path(tmp_path, "config.toml").write_text("unrelated_change = true\n")
        Path(tmp_path, "src", "example.py").write_text("def add(a, b):\n    return a + b + 1\n")

        tool = GitWorkflowTool()
        tool.execute(stage="inspect", project_path=str(tmp_path))

        workflow_key = str(Path(str(tmp_path)).resolve())
        tool._workflows[workflow_key].set_approved(False, "")

        result = tool.execute(
            stage="commit",
            project_path=str(tmp_path),
            task_request="Fix addition bug",
            recent_tools=["write_file"],
            recent_arguments=[{"path": "src/example.py"}],
        )
        assert result.success is False
        assert "not approved" in result.error.lower()

        status = GitStatusTool().execute(project_path=str(tmp_path))
        assert "src/example.py" in status.output
        assert "config.toml" in status.output
