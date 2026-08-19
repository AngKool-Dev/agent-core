from dataclasses import dataclass, field
from typing import Any


@dataclass
class Skill:
    name: str
    path: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    trigger_keywords: list[str] = field(default_factory=list)
    loaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "metadata": self.metadata,
            "trigger_keywords": self.trigger_keywords,
            "loaded": self.loaded,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        return cls(
            name=data["name"],
            path=data["path"],
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            trigger_keywords=data.get("trigger_keywords", []),
            loaded=data.get("loaded", False),
        )
