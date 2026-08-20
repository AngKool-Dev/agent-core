"""Argus tool permissions and safety system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional


class Permission(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PermissionConfig:
    read: str = "allow"
    search: str = "allow"
    write: str = "ask"
    bash: str = "ask"
    git: str = "ask"
    browser: str = "ask"

    def allows(self, tool_name: str) -> bool:
        category = _tool_category(tool_name)
        return getattr(self, category, "ask") != Permission.DENY

    def requires_prompt(self, tool_name: str) -> bool:
        category = _tool_category(tool_name)
        return getattr(self, category, "ask") == Permission.ASK

    def to_dict(self) -> Dict[str, str]:
        return {
            "read": self.read,
            "search": self.search,
            "write": self.write,
            "bash": self.bash,
            "git": self.git,
            "browser": self.browser,
        }


TOOL_CATEGORY_MAP = {
    "read_file": "read",
    "list_dir": "read",
    "grep": "search",
    "glob": "search",
    "write_file": "write",
    "edit_file": "write",
    "bash": "bash",
    "browser": "browser",
}


def _tool_category(tool_name: str) -> str:
    return TOOL_CATEGORY_MAP.get(tool_name, "ask")


class PermissionDeniedError(Exception):
    def __init__(self, tool: str, reason: str = "Permission denied"):
        self.tool = tool
        self.reason = reason
        super().__init__(f"{reason}: {tool}")


def check_permission(
    tool_name: str,
    config: PermissionConfig,
    ask_callback: Optional[Callable[[str, str], bool]] = None,
) -> bool:
    if not config.allows(tool_name):
        raise PermissionDeniedError(tool_name)

    if config.requires_prompt(tool_name):
        if ask_callback is None:
            return False
        category = _tool_category(tool_name)
        prompt = f"Allow Argus to {category} using {tool_name}?"
        return ask_callback(prompt, tool_name)

    return True
