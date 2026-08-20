"""Argus configuration loader."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


DEFAULT_CONFIG_PATHS = [
    Path("argus.toml"),
    Path.home() / ".config" / "argus" / "config.toml",
    Path.home() / ".argus" / "config.toml",
]


class ArgusConfig:
    def __init__(self, config_path: Optional[str] = None):
        self._config: Dict[str, Any] = {}
        self._config_path = config_path

        if config_path:
            self._load(Path(config_path))
        else:
            for path in DEFAULT_CONFIG_PATHS:
                if path.exists():
                    self._load(path)
                    break

        self._apply_defaults()

    def _load(self, path: Path) -> None:
        with open(path, "rb") as f:
            self._config = tomllib.load(f)

    def _apply_defaults(self) -> None:
        defaults = {
            "agent": {
                "default_runtime": "hermes",
                "max_iterations": 10,
                "max_tools": 20,
                "timeout_seconds": 300,
            },
            "skills": {
                "paths": ["D:/agent-core/unified_folder/ObsidianVault/agent-skills/skills"],
            },
            "memory": {
                "backend": "db_obsidian",
                "db_path": "~/.agentcore/memory.db",
                "session_location": "~/.agentcore/sessions",
            },
            "repl": {
                "history_size": 1000,
                "prompt": "argus> ",
            },
        }

        for section, values in defaults.items():
            if section not in self._config:
                self._config[section] = {}
            for key, value in values.items():
                self._config[section].setdefault(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        obj = self._config
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return default
        return obj if obj is not None else default

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        obj = self._config
        for part in parts[:-1]:
            if part not in obj:
                obj[part] = {}
            obj = obj[part]
        obj[parts[-1]] = value

    def save(self, path: Optional[str] = None) -> None:
        target = Path(path or self._config_path or DEFAULT_CONFIG_PATHS[-1])
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            import tomli_w
            with open(target, "w", encoding="utf-8") as f:
                f.write(tomli_w.dumps(self._config))
        except ImportError:
            lines = []
            for section, values in self._config.items():
                lines.append(f"[{section}]")
                for key, value in values.items():
                    if isinstance(value, str):
                        lines.append(f'{key} = "{value}"')
                    elif isinstance(value, bool):
                        lines.append(f"{key} = {str(value).lower()}")
                    elif isinstance(value, list):
                        items = ", ".join(f'"{v}"' for v in value)
                        lines.append(f"{key} = [{items}]")
                    else:
                        lines.append(f"{key} = {value}")
                lines.append("")
            target.write_text("\n".join(lines), encoding="utf-8")

    @property
    def raw(self) -> Dict[str, Any]:
        return dict(self._config)
