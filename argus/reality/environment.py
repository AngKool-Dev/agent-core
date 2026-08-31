"""Production environment capture for ARGUS qualification."""

import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from argus.reality.models import EnvironmentInfo


# Safe environment variable names (never capture values of secrets)
SAFE_ENV_VAR_PREFIXES = [
    "ARGUS_",
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "LC_",
    "TZ",
    "TERM",
    "SHELL",
    "PYTHON",
    "VIRTUAL_ENV",
    "CONDA",
    "NODE",
    "NPM",
    "GOPATH",
    "RUSTUP",
    "CARGO",
    "JAVA_HOME",
    "DOTNET_",
    "GOOS",
    "GOARCH",
]

SAFE_ENV_VAR_NAMES = {
    "OS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
    "NUMBER_OF_PROCESSORS", "COMPUTERNAME", "USERNAME", "USERDOMAIN",
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
    "PATHEXT", "COMSPEC", "PROMPT", "HOSTNAME",
}

# Secret patterns to exclude
SECRET_ENV_VAR_PATTERNS = [
    "KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PWD",
    "CREDENTIAL", "AUTH", "CERT", "PRIVATE", "API_KEY",
    "ACCESS_TOKEN", "REFRESH_TOKEN", "SESSION", "COOKIE",
    "SIGNATURE", "HASH", "SALT", "ENCRYPT", "DECRYPT",
]


def _is_safe_env_var(name: str) -> bool:
    """Check if an environment variable name is safe to capture."""
    upper_name = name.upper()

    # Check against known safe names
    if upper_name in SAFE_ENV_VAR_NAMES:
        return True

    # Check against safe prefixes
    for prefix in SAFE_ENV_VAR_PREFIXES:
        if upper_name.startswith(prefix):
            return True

    # Check against secret patterns
    for pattern in SECRET_ENV_VAR_PATTERNS:
        if pattern in upper_name:
            return False

    return False


def _get_argus_version() -> str:
    """Get ARGUS version."""
    try:
        from argus import __version__
        return __version__
    except Exception:
        return "unknown"


def _get_git_revision() -> str:
    """Get current git revision."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_package_installation_mode() -> str:
    """Detect how ARGUS is installed."""
    try:
        import argus
        argus_path = Path(argus.__file__).resolve()

        # Check if installed as editable/development
        if "site-packages" in str(argus_path):
            return "package"
        elif ".venv" in str(argus_path) or "venv" in str(argus_path):
            return "venv"
        else:
            return "development"
    except Exception:
        return "unknown"


def _check_filesystem_capabilities() -> Dict[str, bool]:
    """Check filesystem capabilities."""
    capabilities = {
        "read": False,
        "write": False,
        "execute": False,
        "symlink": False,
        "hardlink": False,
        "temp_dir": False,
    }

    try:
        # Test read
        test_file = Path(__file__)
        capabilities["read"] = test_file.exists() and test_file.is_file()

        # Test write
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            capabilities["write"] = True
            temp_path = f.name
        os.unlink(temp_path)

        # Test execute
        capabilities["execute"] = os.access(sys.executable, os.X_OK)

        # Test symlink
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                target = Path(tmpdir) / "target.txt"
                target.write_text("test")
                link = Path(tmpdir) / "link.txt"
                link.symlink_to(target)
                capabilities["symlink"] = link.exists()
        except Exception:
            capabilities["symlink"] = False

        # Test temp dir
        import tempfile
        capabilities["temp_dir"] = Path(tempfile.gettempdir()).exists()

    except Exception:
        pass

    return capabilities


def _check_subprocess_availability() -> Dict[str, bool]:
    """Check which subprocess tools are available."""
    tools = [
        "git", "python", "pip", "npm", "node", "cargo", "rustc",
        "go", "javac", "java", "dotnet", "docker", "kubectl",
        "curl", "wget", "ssh", "tar", "zip", "unzip",
    ]

    availability = {}
    for tool in tools:
        availability[tool] = _is_tool_available(tool)

    return availability


def _is_tool_available(tool: str) -> bool:
    """Check if a command-line tool is available."""
    try:
        import subprocess
        result = subprocess.run(
            ["where" if os.name == "nt" else "which", tool],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_provider_configurations() -> Dict[str, bool]:
    """Check which providers are configured (without capturing secrets)."""
    providers = {
        "openrouter": False,
        "gemini": False,
        "groq": False,
        "cerebras": False,
        "ollama": False,
        "openai": False,
        "anthropic": False,
        "gateway": False,
    }

    try:
        from argus.config import ArgusConfig
        config = ArgusConfig()

        # Check model hub providers
        hub_providers = config.get("model_hub.providers", {})
        for provider in providers:
            if provider in hub_providers:
                provider_config = hub_providers[provider]
                providers[provider] = provider_config.get("enabled", False)

        # Check gateway
        gateway_config = config.get("gateway", {})
        if gateway_config and gateway_config.get("base_url") and gateway_config.get("api_key"):
            providers["gateway"] = True

    except Exception:
        pass

    return providers


def _check_mcp_configurations() -> Dict[str, bool]:
    """Check MCP configuration presence."""
    mcp_configs = {
        "filesystem": False,
        "git": False,
        "github": False,
        "postgres": False,
        "custom": False,
    }

    try:
        from argus.config import ArgusConfig
        config = ArgusConfig()

        mcp_servers = config.get("mcp.servers", {})
        for server_name in mcp_configs:
            if server_name in mcp_servers:
                mcp_configs[server_name] = True

        # Check for any custom servers
        if mcp_servers:
            mcp_configs["custom"] = len(mcp_servers) > 0

    except Exception:
        pass

    return mcp_configs


class ProductionEnvironment:
    """Captures and reports production environment information."""

    def __init__(self):
        self._info: Optional[EnvironmentInfo] = None

    def snapshot(self) -> EnvironmentInfo:
        """Capture a snapshot of the current production environment."""
        info = EnvironmentInfo()

        # Python info
        info.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # OS info
        info.os_name = platform.system()
        info.os_version = platform.version()
        info.architecture = platform.machine()

        # Paths
        info.executable_path = sys.executable
        info.working_directory = str(Path.cwd())

        # ARGUS info
        info.argus_version = _get_argus_version()
        info.git_revision = _get_git_revision()
        info.package_installation_mode = _get_package_installation_mode()

        # Safe environment variables only
        for key, value in os.environ.items():
            if _is_safe_env_var(key):
                info.environment_variables[key] = value

        # Provider configurations (presence only)
        info.provider_configurations = _check_provider_configurations()

        # MCP configurations
        info.mcp_configurations = _check_mcp_configurations()

        # Filesystem capabilities
        info.filesystem_capabilities = _check_filesystem_capabilities()

        # Subprocess availability
        info.subprocess_availability = _check_subprocess_availability()

        # Shell
        info.shell_available = os.environ.get("COMSPEC") is not None or os.environ.get("SHELL") is not None

        # Terminal
        info.terminal_encoding = sys.getdefaultencoding()
        try:
            import locale as locale_mod
            loc = locale_mod.getlocale()
            info.locale = ".".join(str(x) for x in loc if x) or "unknown"
        except Exception:
            info.locale = "unknown"
        info.path_separator = os.sep
        info.timezone = datetime.now().astimezone().tzname() or "unknown"

        self._info = info
        return info

    def to_dict(self) -> Dict[str, Any]:
        """Convert environment info to dictionary."""
        if not self._info:
            self.snapshot()
        return self._info.to_dict() if self._info else {}

    def safe_summary(self) -> str:
        """Generate a safe summary string (no secrets)."""
        if not self._info:
            self.snapshot()

        if not self._info:
            return "Environment capture failed"

        lines = [
            "Production Environment Summary",
            "=" * 40,
            f"Python: {self._info.python_version}",
            f"OS: {self._info.os_name} {self._info.os_version}",
            f"Architecture: {self._info.architecture}",
            f"ARGUS Version: {self._info.argus_version}",
            f"Git Revision: {self._info.git_revision}",
            f"Installation: {self._info.package_installation_mode}",
            f"Working Directory: {self._info.working_directory}",
            f"Terminal Encoding: {self._info.terminal_encoding}",
            f"Path Separator: {self._info.path_separator}",
            f"Timezone: {self._info.timezone}",
            "",
            "Providers Configured:",
        ]

        for provider, configured in self._info.provider_configurations.items():
            status = "yes" if configured else "no"
            lines.append(f"  {provider}: {status}")

        lines.extend(["", "MCP Servers Configured:"])
        for server, configured in self._info.mcp_configurations.items():
            status = "yes" if configured else "no"
            lines.append(f"  {server}: {status}")

        lines.extend(["", "Filesystem Capabilities:"])
        for cap, available in self._info.filesystem_capabilities.items():
            status = "yes" if available else "no"
            lines.append(f"  {cap}: {status}")

        lines.extend(["", "Subprocess Availability:"])
        for tool, available in self._info.subprocess_availability.items():
            if available:
                lines.append(f"  {tool}: yes")

        return "\n".join(lines)

    @property
    def info(self) -> Optional[EnvironmentInfo]:
        """Get the captured environment info."""
        return self._info


def capture_environment() -> EnvironmentInfo:
    """Convenience function to capture the production environment."""
    env = ProductionEnvironment()
    return env.snapshot()


def get_safe_summary() -> str:
    """Convenience function to get a safe environment summary."""
    env = ProductionEnvironment()
    return env.safe_summary()
