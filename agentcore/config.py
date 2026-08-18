"""
AgentCore configuration system.

Provides a single configuration-loading path:
    ConfigLoader.discover() / ConfigLoader.load()
    → AgentCoreConfig
    → AgentConfig, SkillConfig, MemoryConfig, ToolLimits, VerificationConfig

No component other than ConfigLoader parses TOML.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Cross-platform user config directory
# ---------------------------------------------------------------------------

def user_config_dir() -> Path:
    """Return the platform-appropriate user-level config directory."""
    if os.name == "nt":
        # Windows: %LOCALAPPDATA%/agentcore/
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "agentcore"
        # Fallback: ~/AppData/Local/agentcore/
        return Path.home() / "AppData" / "Local" / "agentcore"
    elif os.name == "posix":
        # Linux: ~/.config/agentcore/
        # macOS: ~/Library/Application Support/agentcore/
        if sys_platform_darwin():
            return Path.home() / "Library" / "Application Support" / "agentcore"
        return Path.home() / ".config" / "agentcore"
    return Path.home() / ".agentcore"


def sys_platform_darwin() -> bool:
    import platform
    return platform.system() == "Darwin"


def user_data_dir() -> Path:
    """Return the platform-appropriate user-level data directory (for memory DB etc.)."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "agentcore"
        return Path.home() / "AppData" / "Local" / "agentcore"
    elif os.name == "posix":
        if sys_platform_darwin():
            return Path.home() / "Library" / "Application Support" / "agentcore"
        return Path.home() / ".local" / "share" / "agentcore"
    return Path.home() / ".agentcore"


# ---------------------------------------------------------------------------
# Typed config sections
# ---------------------------------------------------------------------------

@dataclass
class SkillConfig:
    """Skill discovery configuration."""
    paths: List[str] = field(default_factory=list)


@dataclass
class MemoryConfig:
    """Memory backend configuration."""
    backend: str = "db_obsidian"
    db_path: str = ""  # empty = use default per-platform path


@dataclass
class ToolLimits:
    """Tool and iteration limits."""
    max_iterations: int = 10
    max_tool_calls: int = 50
    max_runtime_seconds: int = 300
    timeout: int = 300


@dataclass
class VerificationConfig:
    """Verification gate settings."""
    run_format_check: bool = True
    run_build_check: bool = True
    run_tests: bool = True


@dataclass
class AgentCoreConfig:
    """
    Top-level typed configuration object.

    Built from TOML via ConfigLoader. All sections are optional;
    missing values fall back to built-in defaults.
    """
    # Agent runtime settings
    default_runtime: str = "hermes"
    model: Optional[str] = None
    provider: Optional[str] = None

    # Skill discovery
    skill_paths: List[str] = field(default_factory=list)

    # Memory
    memory_backend: str = "db_obsidian"
    memory_db_path: str = ""

    # Tool limits
    max_iterations: int = 10
    max_tool_calls: int = 50
    max_runtime_seconds: int = 300
    timeout: int = 300

    # Verification
    run_format_check: bool = True
    run_build_check: bool = True
    run_tests: bool = True
    verification_scope: str = "project"

    # Project discovery
    max_context_files: int = 50
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "*.pyc", "*.pyo", "__pycache__", ".git", "*.egg-info",
        "node_modules", ".venv", "venv",
    ])

    def to_agent_config(self) -> "AgentConfig":
        """Extract the subset relevant to AgentConfig."""
        from agentcore.agent import AgentConfig
        return AgentConfig(
            model=self.model,
            provider=self.provider,
            max_iterations=self.max_iterations,
            max_tool_calls=self.max_tool_calls,
            max_runtime_seconds=self.max_runtime_seconds,
            timeout=self.timeout,
            enable_verification=self.run_format_check or self.run_build_check or self.run_tests,
            run_format_check=self.run_format_check,
            run_build_check=self.run_build_check,
            run_tests=self.run_tests,
            verification_scope=self.verification_scope,
        )

    @classmethod
    def defaults(cls) -> "AgentCoreConfig":
        """Return a config populated with built-in defaults and default paths."""
        return cls(
            default_runtime="hermes",
            memory_db_path=str(user_data_dir() / "memory.db"),
            skill_paths=_default_skill_paths(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_runtime": self.default_runtime,
            "model": self.model,
            "provider": self.provider,
            "skill_paths": list(self.skill_paths),
            "memory_backend": self.memory_backend,
            "memory_db_path": self.memory_db_path,
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
            "max_runtime_seconds": self.max_runtime_seconds,
            "timeout": self.timeout,
            "run_format_check": self.run_format_check,
            "run_build_check": self.run_build_check,
            "run_tests": self.run_tests,
            "max_context_files": self.max_context_files,
            "exclude_patterns": list(self.exclude_patterns),
        }


def _default_skill_paths() -> List[str]:
    """Return default skill search directories, platform-appropriate."""
    paths = []

    # Project-local skills/ directory
    project_local = Path("skills")
    if project_local.exists():
        paths.append(str(project_local.resolve()))

    # User-level skills directory
    user_skills = user_data_dir() / "skills"
    paths.append(str(user_skills))

    # Obsidian vault agent-skills (if it exists)
    obsidian_skills = Path.home() / "ObsidianVault" / "agent-skills" / "skills"
    if obsidian_skills.exists():
        paths.append(str(obsidian_skills))

    return paths


# ---------------------------------------------------------------------------
# Config discovery and loading
# ---------------------------------------------------------------------------

# Environment variable for skill path override
SKILLS_ENV_VAR = "AGENTCORE_SKILLS_PATH"

# Path separator for multiple skill directories in env var
SKILLS_PATH_SEP = os.pathsep


class ConfigLoader:
    """
    Discovers and loads AgentCore configuration from TOML.

    Discovery order (first match wins):
    1. Explicit config path (passed to load())
    2. Project-local config: ./agentcore.toml or ./config/agentcore.toml
    3. User-level config: {user_config_dir}/agentcore.toml
    4. Built-in defaults
    """

    @staticmethod
    def discover(project_path: Optional[Path] = None) -> AgentCoreConfig:
        """
        Discover configuration in priority order.

        Returns a fully-populated AgentCoreConfig.
        """
        project = project_path or Path.cwd()

        # 1. Try project-local configs
        candidates = [
            project / "agentcore.toml",
            project / "config" / "agentcore.toml",
            project / "config" / "agent.toml",
        ]

        for candidate in candidates:
            if candidate.exists():
                config = ConfigLoader.load(candidate)
                # Fill in any missing defaults
                ConfigLoader._apply_defaults(config)
                return config

        # 2. Try user-level config
        user_config = user_config_dir() / "agentcore.toml"
        if user_config.exists():
            config = ConfigLoader.load(user_config)
            ConfigLoader._apply_defaults(config)
            return config

        # 3. Built-in defaults
        config = AgentCoreConfig.defaults()
        return config

    @staticmethod
    def load(config_path: Path) -> AgentCoreConfig:
        """Load configuration from a specific TOML file."""
        config_path = Path(config_path).expanduser().resolve()

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Malformed TOML in {config_path}: {e}") from e
        except Exception as e:
            raise ValueError(f"Error reading config {config_path}: {e}") from e

        return ConfigLoader._parse_toml(data)

    @staticmethod
    def _parse_toml(data: Dict[str, Any]) -> AgentCoreConfig:
        """Parse a TOML dict into an AgentCoreConfig."""
        config = AgentCoreConfig()

        # Agent section
        agent_data = data.get("agent", {})
        if agent_data:
            config.default_runtime = agent_data.get("default_runtime", config.default_runtime)
            config.model = agent_data.get("model", config.model)
            config.provider = agent_data.get("provider", config.provider)

        # Skill paths
        skill_data = data.get("skill_paths", {})
        if skill_data:
            paths = []
            primary = skill_data.get("primary", "")
            if primary:
                paths.append(str(Path(primary).expanduser()))
            extra = skill_data.get("extra", [])
            if isinstance(extra, list):
                paths.extend(str(Path(p).expanduser()) for p in extra)
            config.skill_paths = paths

        # Memory
        mem_data = data.get("memory", {})
        if mem_data:
            config.memory_backend = mem_data.get("backend", config.memory_backend)
            db_path = mem_data.get("db_path", "")
            if db_path:
                config.memory_db_path = str(Path(db_path).expanduser())
            else:
                config.memory_db_path = str(user_data_dir() / "memory.db")

        # Tool limits
        limits_data = data.get("tool_limits", {})
        if limits_data:
            config.max_iterations = limits_data.get("max_iterations", config.max_iterations)
            # Accept both max_tool_calls (canonical) and max_tools_per_task (legacy alias)
            config.max_tool_calls = limits_data.get(
                "max_tool_calls",
                limits_data.get("max_tools_per_task", config.max_tool_calls),
            )
            config.max_runtime_seconds = limits_data.get(
                "max_runtime_seconds", limits_data.get("timeout_seconds", config.max_runtime_seconds)
            )
            config.timeout = limits_data.get("timeout", config.timeout)

        # Verification
        verify_data = data.get("verification", {})
        if verify_data:
            config.run_format_check = verify_data.get("run_format_check", config.run_format_check)
            config.run_build_check = verify_data.get("run_build_check", config.run_build_check)
            config.run_tests = verify_data.get("run_tests", config.run_tests)
            config.verification_scope = verify_data.get("verification_scope", config.verification_scope)

        # Project discovery
        discovery_data = data.get("project_discovery", {})
        if discovery_data:
            config.max_context_files = discovery_data.get("max_context_files", config.max_context_files)
            patterns = discovery_data.get("exclude_patterns", [])
            if isinstance(patterns, list):
                config.exclude_patterns = patterns

        # Also check root-level [tool_limits] for backwards compat with old config format
        old_limits = data.get("tool_limits", {})
        # Already handled above — but also check if there's a flat top-level section

        return config

    @staticmethod
    def _apply_defaults(config: AgentCoreConfig) -> None:
        """Fill in missing defaults on a partially-loaded config."""
        if not config.memory_db_path:
            config.memory_db_path = str(user_data_dir() / "memory.db")

        if not config.skill_paths:
            config.skill_paths = _default_skill_paths()


def resolve_skill_paths(config: Optional[AgentCoreConfig] = None) -> List[str]:
    """
    Resolve skill search paths with environment-variable override.

    Precedence:
    1. AGENTCORE_SKILLS_PATH environment variable
    2. Explicit configured paths in config.skill_paths
    3. Default discovery (project-local + user-level + Obsidian vault)
    4. Empty list (no skills)
    """
    # 1. Environment override
    env_paths = os.environ.get(SKILLS_ENV_VAR)
    if env_paths:
        return [p.strip() for p in env_paths.split(SKILLS_PATH_SEP) if p.strip()]

    # 2. Configured paths
    if config and config.skill_paths:
        resolved = []
        for p in config.skill_paths:
            path = Path(p).expanduser()
            resolved.append(str(path))
        return resolved

    # 3. Default discovery
    if config is None:
        config = AgentCoreConfig.defaults()

    return [str(Path(p).expanduser()) for p in config.skill_paths]
