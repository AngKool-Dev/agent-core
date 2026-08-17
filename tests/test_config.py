"""
Tests for AgentCore configuration system (Phase 3).

Tests cover:
- Configuration loading (valid TOML, missing config, malformed TOML, explicit path)
- AgentConfig mapping from AgentCoreConfig
- Skill path resolution (configured, multiple, env override, missing, relative, absolute)
- Cross-platform behavior (no hardcoded /home/era or C:\\Users\\Administrator paths)
- CLI --config flag integration
"""

import os
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from agentcore.config import (
    AgentCoreConfig,
    ConfigLoader,
    SkillConfig,
    MemoryConfig,
    ToolLimits,
    VerificationConfig,
    user_config_dir,
    user_data_dir,
    resolve_skill_paths,
    SKILLS_ENV_VAR,
)
from agentcore import Agent, AgentConfig, create_agent


class TestConfigLoading:
    """Configuration loading from TOML."""

    def test_load_valid_toml(self, tmp_path):
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [agent]
            default_runtime = "hermes"
            model = "claude-sonnet-4"

            [tool_limits]
            max_iterations = 20
            max_tool_calls = 15
        """), encoding="utf-8")

        config = ConfigLoader.load(config_file)
        assert config.default_runtime == "hermes"
        assert config.model == "claude-sonnet-4"
        assert config.max_iterations == 20
        assert config.max_tool_calls == 15

    def test_load_missing_config_raises(self, tmp_path):
        config_file = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load(config_file)

    def test_load_malformed_toml_raises(self, tmp_path):
        config_file = tmp_path / "bad.toml"
        config_file.write_text("[agent\nthis is not = valid = toml\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Malformed TOML"):
            ConfigLoader.load(config_file)

    def test_discover_explicit_config_path(self, tmp_path):
        """Config passed explicitly takes priority."""
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [agent]
            default_runtime = "kilo"
            [tool_limits]
            max_iterations = 5
        """), encoding="utf-8")

        config = ConfigLoader.load(config_file)
        assert config.default_runtime == "kilo"
        assert config.max_iterations == 5

    def test_discover_project_config(self, tmp_path):
        """Project-local config is discovered automatically."""
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [agent]
            default_runtime = "opencode"
        """), encoding="utf-8")

        config = ConfigLoader.discover(project_path=tmp_path)
        assert config.default_runtime == "opencode"

    def test_discover_project_config_in_config_dir(self, tmp_path):
        """Project config in config/ directory is discovered."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [agent]
            default_runtime = "opencode"
        """), encoding="utf-8")

        config = ConfigLoader.discover(project_path=tmp_path)
        assert config.default_runtime == "opencode"

    def test_discover_defaults_when_no_config(self, tmp_path):
        """No config file present — defaults are returned."""
        config = ConfigLoader.discover(project_path=tmp_path)
        assert config.default_runtime == "hermes"
        assert config.max_iterations == 10
        assert config.max_tool_calls == 50

    def test_discover_with_empty_project(self, tmp_path):
        """Empty project directory should return defaults, not crash."""
        config = ConfigLoader.discover(project_path=tmp_path)
        assert isinstance(config, AgentCoreConfig)
        assert config.default_runtime == "hermes"

    def test_config_to_dict(self):
        config = AgentCoreConfig(default_runtime="hermes", model="test")
        data = config.to_dict()
        assert data["default_runtime"] == "hermes"
        assert data["model"] == "test"
        assert isinstance(data["skill_paths"], list)


class TestAgentConfigMapping:
    """Values from TOML reach AgentConfig correctly."""

    def test_to_agent_config_basic(self):
        core_config = AgentCoreConfig(
            model="claude-sonnet-4",
            provider="anthropic",
            max_iterations=20,
            max_tool_calls=15,
        )
        agent_config = core_config.to_agent_config()
        assert agent_config.model == "claude-sonnet-4"
        assert agent_config.provider == "anthropic"
        assert agent_config.max_iterations == 20
        assert agent_config.max_tool_calls == 15

    def test_to_agent_config_verification(self):
        core_config = AgentCoreConfig(
            run_format_check=True,
            run_build_check=False,
            run_tests=True,
        )
        agent_config = core_config.to_agent_config()
        assert agent_config.run_format_check is True
        assert agent_config.run_build_check is False
        assert agent_config.run_tests is True
        # enable_verification is True if any verification option is True
        assert agent_config.enable_verification is True

    def test_to_agent_config_verification_all_off(self):
        core_config = AgentCoreConfig(
            run_format_check=False,
            run_build_check=False,
            run_tests=False,
        )
        agent_config = core_config.to_agent_config()
        assert agent_config.enable_verification is False

    def test_max_tool_calls_mapping_from_toml(self, tmp_path):
        """The TOML uses max_tool_calls — verify it maps correctly."""
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [tool_limits]
            max_tool_calls = 7
        """), encoding="utf-8")

        config = ConfigLoader.load(config_file)
        assert config.max_tool_calls == 7
        agent_config = config.to_agent_config()
        assert agent_config.max_tool_calls == 7

    def test_max_tools_per_task_legacy_alias(self, tmp_path):
        """max_tools_per_task in TOML should map to max_tool_calls."""
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [tool_limits]
            max_tools_per_task = 12
        """), encoding="utf-8")

        config = ConfigLoader.load(config_file)
        assert config.max_tool_calls == 12

    def test_memory_db_path_from_toml(self, tmp_path):
        db_path = tmp_path / "memory.db"
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent(f"""
            [memory]
            backend = "db_obsidian"
            db_path = "{db_path.as_posix()}"
        """), encoding="utf-8")

        config = ConfigLoader.load(config_file)
        assert config.memory_backend == "db_obsidian"
        assert str(db_path) in config.memory_db_path


class TestSkillPaths:
    """Skill path resolution and precedence."""

    def test_configured_skill_directory(self, tmp_path):
        skills_dir = tmp_path / "my-skills"
        skills_dir.mkdir()
        (skills_dir / "test-skill").mkdir()
        (skills_dir / "test-skill" / "SKILL.md").write_text("# test-skill\n")

        config = AgentCoreConfig(skill_paths=[str(skills_dir)])
        paths = resolve_skill_paths(config)
        assert str(skills_dir) in paths

    def test_multiple_skill_directories(self, tmp_path):
        dir1 = tmp_path / "skills1"
        dir2 = tmp_path / "skills2"
        dir1.mkdir()
        dir2.mkdir()

        config = AgentCoreConfig(skill_paths=[str(dir1), str(dir2)])
        paths = resolve_skill_paths(config)
        assert str(dir1) in paths
        assert str(dir2) in paths

    def test_environment_override(self, tmp_path):
        """AGENTCORE_SKILLS_PATH takes priority over config."""
        env_dir = tmp_path / "env-skills"
        env_dir.mkdir()

        config = AgentCoreConfig(skill_paths=[str(tmp_path / "config-skills")])

        old_val = os.environ.pop(SKILLS_ENV_VAR, None)
        try:
            os.environ[SKILLS_ENV_VAR] = str(env_dir)
            paths = resolve_skill_paths(config)
            assert str(env_dir) in paths
            # Config paths should not be in the result when env override is set
            assert str(tmp_path / "config-skills") not in paths
        finally:
            if old_val is not None:
                os.environ[SKILLS_ENV_VAR] = old_val
            else:
                os.environ.pop(SKILLS_ENV_VAR, None)

    def test_environment_override_multiple_paths(self, tmp_path):
        """Env var with OS-specific separator supports multiple paths."""
        dir1 = tmp_path / "env-skills1"
        dir2 = tmp_path / "env-skills2"
        dir1.mkdir()
        dir2.mkdir()

        old_val = os.environ.pop(SKILLS_ENV_VAR, None)
        try:
            os.environ[SKILLS_ENV_VAR] = str(dir1) + os.pathsep + str(dir2)
            paths = resolve_skill_paths(None)
            assert str(dir1) in paths
            assert str(dir2) in paths
        finally:
            if old_val is not None:
                os.environ[SKILLS_ENV_VAR] = old_val
            else:
                os.environ.pop(SKILLS_ENV_VAR, None)

    def test_missing_directory_does_not_crash(self, tmp_path):
        """Missing skill directories must not crash AgentCore."""
        nonexistent = tmp_path / "does-not-exist"
        config = AgentCoreConfig(skill_paths=[str(nonexistent)])
        paths = resolve_skill_paths(config)
        # The path is included (registry will skip it), but no crash
        assert isinstance(paths, list)

    def test_relative_directory(self, tmp_path):
        """Relative skill paths should be resolved."""
        config = AgentCoreConfig(skill_paths=["./my-skills"])
        paths = resolve_skill_paths(config)
        # Should not contain /home/era
        assert not any("/home/era" in p for p in paths)

    def test_absolute_directory(self, tmp_path):
        abs_dir = tmp_path / "abs-skills"
        abs_dir.mkdir()
        config = AgentCoreConfig(skill_paths=[str(abs_dir)])
        paths = resolve_skill_paths(config)
        assert str(abs_dir) in paths

    def test_missing_config_falls_back_to_defaults(self, tmp_path):
        """When no config exists, default paths are used."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SKILLS_ENV_VAR, None)
            config = ConfigLoader.discover(project_path=tmp_path)
            paths = resolve_skill_paths(config)
            # Should have at least one default path
            assert len(paths) >= 1
            # None should contain /home/era
            assert not any("/home/era" in p for p in paths)

    def test_duplicate_skill_handling(self, tmp_path):
        """Duplicate paths in config should be handled gracefully."""
        dir1 = tmp_path / "skills"
        dir1.mkdir()
        config = AgentCoreConfig(skill_paths=[str(dir1), str(dir1)])
        paths = resolve_skill_paths(config)
        # Path may appear twice but shouldn't crash
        assert str(dir1) in paths


class TestCrossPlatformPaths:
    """No hardcoded developer paths in production code."""

    def test_user_config_dir_is_portable(self):
        """user_config_dir should use Path.home(), not hardcoded paths."""
        import platform
        path = user_config_dir()
        assert isinstance(path, Path)
        # Should not contain /home/era
        assert "/home/era" not in str(path)
        # On Windows, should use LOCALAPADATA or AppData
        if os.name == "nt":
            assert "Administrator" not in str(path) or "AppData" in str(path)

    def test_user_data_dir_is_portable(self):
        path = user_data_dir()
        assert isinstance(path, Path)
        assert "/home/era" not in str(path)

    def test_resolve_skill_paths_no_hardcoded_user(self, tmp_path):
        """resolve_skill_paths should not produce /home/era paths."""
        old_val = os.environ.pop(SKILLS_ENV_VAR, None)
        try:
            config = AgentCoreConfig(skill_paths=[str(tmp_path / "skills")])
            paths = resolve_skill_paths(config)
            assert not any("/home/era" in p for p in paths)
        finally:
            if old_val is not None:
                os.environ[SKILLS_ENV_VAR] = old_val
            else:
                os.environ.pop(SKILLS_ENV_VAR, None)

    def test_default_skill_paths_no_hardcoded(self):
        """_default_skill_paths should not hardcode /home/era."""
        from agentcore.config import _default_skill_paths
        paths = _default_skill_paths()
        assert not any("/home/era" in p for p in paths)


class TestAgentWithConfig:
    """Agent uses configuration for skill paths and tool limits."""

    def test_agent_uses_config_for_max_tool_calls(self, tmp_path):
        """AgentConfig.max_tool_calls from TOML should reach the Agent."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.memory import MemoryBackend, MemoryManager

        class InMemoryBackend(MemoryBackend):
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

        core_config = AgentCoreConfig(
            max_iterations=3,
            max_tool_calls=2,
        )
        agent_config = core_config.to_agent_config()
        agent_config.enable_verification = False

        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())

        agent = Agent(
            runtime=runtime,
            memory=memory,
            config=agent_config,
            project_path=tmp_path,
            agentcore_config=core_config,
        )
        assert agent.config.max_tool_calls == 2

    def test_agent_no_hardcoded_skill_paths(self):
        """Agent source should not contain /home/era paths."""
        import inspect
        source = inspect.getsource(Agent)
        assert "/home/era" not in source, \
            "Agent source must not contain hardcoded /home/era paths"

    def test_create_agent_loads_config(self, tmp_path):
        """create_agent should discover and load config."""
        from tests.test_mock_runtime import MockRuntime
        from agentcore.memory import MemoryBackend, MemoryManager

        class InMemoryBackend(MemoryBackend):
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

        # Create a project-level config
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [agent]
            model = "custom-model"
            [tool_limits]
            max_iterations = 15
        """), encoding="utf-8")

        runtime = MockRuntime(responses=["Done"])
        memory = MemoryManager(InMemoryBackend())

        agent = create_agent(
            runtime=runtime,
            memory=memory,
            project_path=tmp_path,
        )

        # Config should be discovered from the project
        assert agent._agentcore_config.default_runtime == "hermes"  # default, not overridden
        assert agent._agentcore_config.max_iterations == 15


class TestCLIconfigIntegration:
    """CLI --config flag integration."""

    def test_cli_parse_config_arg(self):
        from agentcore.cli.main import parse_args
        args = parse_args(["--config", "/custom/config.toml", "do a thing"])
        assert args.config == "/custom/config.toml"
        assert args.request == "do a thing"

    def test_cli_config_arg_optional(self):
        from agentcore.cli.main import parse_args
        args = parse_args(["do a thing"])
        assert args.config is None

    def test_cli_uses_config_for_limits(self, tmp_path):
        """CLI should build AgentConfig from loaded config."""
        config_file = tmp_path / "agentcore.toml"
        config_file.write_text(textwrap.dedent("""
            [tool_limits]
            max_iterations = 42
        """), encoding="utf-8")

        core_config = ConfigLoader.load(config_file)
        agent_config = core_config.to_agent_config()
        assert agent_config.max_iterations == 42
