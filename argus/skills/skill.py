"""Argus skill abstraction."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Skill:
    name: str
    description: str
    instructions: str = ""
    triggers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    path: Optional[Path] = None

    def matches(self, text: str) -> bool:
        text_lower = text.lower()
        return any(trigger.lower() in text_lower for trigger in self.triggers)

    def to_context(self) -> str:
        parts = [f"## Skill: {self.name}", self.description]
        if self.instructions:
            parts.extend(["", self.instructions])
        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "triggers": self.triggers,
            "metadata": self.metadata,
            "path": str(self.path) if self.path else None,
        }
