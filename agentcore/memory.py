from abc import ABC, abstractmethod
from typing import Any, List, Optional


class MemoryBackend(ABC):
    @abstractmethod
    def search(self, query: str, project: Optional[str] = None, limit: int = 20) -> List[dict[str, Any]]:
        pass

    @abstractmethod
    def store(self, type: str, content: str, project: Optional[str] = None, importance: float = 0.5) -> dict[str, Any]:
        pass

    @abstractmethod
    def update(self, memory_id: str, content: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def list(self, project: Optional[str] = None, type: Optional[str] = None, limit: int = 50) -> List[dict[str, Any]]:
        pass


class MemoryManager:
    def __init__(self, backend: MemoryBackend):
        self._backend = backend

    def search(self, query: str, project: Optional[str] = None, limit: int = 20) -> List[dict[str, Any]]:
        return self._backend.search(query, project, limit)

    def store(self, type: str, content: str, project: Optional[str] = None, importance: float = 0.5) -> dict[str, Any]:
        return self._backend.store(type, content, project, importance)

    def update(self, memory_id: str, content: str) -> dict[str, Any]:
        return self._backend.update(memory_id, content)

    def list(self, project: Optional[str] = None, type: Optional[str] = None, limit: int = 50) -> List[dict[str, Any]]:
        return self._backend.list(project, type, limit)

    def store_decision(self, decision: str, project: str, context: Optional[str] = None) -> dict[str, Any]:
        content = f"{context}\n\nDecision: {decision}" if context else decision
        return self.store("decision", content, project, importance=0.8)

    def store_lesson(self, lesson: str, project: str) -> dict[str, Any]:
        return self.store("lesson", lesson, project, importance=0.7)

    def store_project_architecture(self, architecture: str, project: str) -> dict[str, Any]:
        return self.store("project_architecture", architecture, project, importance=0.9)

    def retrieve_relevant_memory(self, query: str, project: str, types: Optional[List[str]] = None) -> str:
        results = self.search(query, project, limit=10)
        relevant = [r for r in results if types is None or r.get("type") in types]
        return "\n\n---\n\n".join(r.get("content", "") for r in relevant)