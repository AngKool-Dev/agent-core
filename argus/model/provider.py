"""Argus model provider abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ModelResponse:
    content: str
    model: str
    usage: Dict[str, int] = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {}


class ModelProvider(ABC):
    @abstractmethod
    def complete(self, messages: List[Message], model: Optional[str] = None, **kwargs) -> ModelResponse:
        ...

    @abstractmethod
    def stream(self, messages: List[Message], model: Optional[str] = None, **kwargs):
        ...
