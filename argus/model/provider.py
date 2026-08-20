"""Argus model provider abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ToolCall:
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str = ""


@dataclass
class ModelResponse:
    content: str
    model: str
    finish_reason: str = "stop"
    tool_calls: List[ToolCall] = field(default_factory=list)
    reasoning: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "finish_reason": self.finish_reason,
            "tool_calls": [tc.__dict__ for tc in self.tool_calls],
            "reasoning": self.reasoning,
            "usage": self.usage,
        }


class ModelProvider(ABC):
    @abstractmethod
    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        ...

    @abstractmethod
    def stream(self, messages: List[Message], model: Optional[str] = None, **kwargs):
        ...
