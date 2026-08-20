"""Argus conversation context."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationContext:
    def __init__(self, max_messages: int = 100):
        self._messages: List[Message] = []
        self._max_messages = max_messages

    def add_user(self, content: str, **metadata) -> Message:
        msg = Message(role="user", content=content, metadata=metadata)
        self._messages.append(msg)
        self._trim()
        return msg

    def add_assistant(self, content: str, **metadata) -> Message:
        msg = Message(role="assistant", content=content, metadata=metadata)
        self._messages.append(msg)
        self._trim()
        return msg

    def add_system(self, content: str, **metadata) -> Message:
        msg = Message(role="system", content=content, metadata=metadata)
        self._messages.append(msg)
        self._trim()
        return msg

    def history(self, last_n: Optional[int] = None) -> List[Message]:
        if last_n:
            return self._messages[-last_n:]
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def to_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "metadata": m.metadata,
            }
            for m in self._messages
        ]

    def _trim(self) -> None:
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]
