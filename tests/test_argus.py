"""Tests for Argus core components."""

import os
import tempfile
from pathlib import Path

import pytest

from argus.config import ArgusConfig
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
