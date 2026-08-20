"""Argus memory adapter for AgentCore DB-Obsidian."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentcore.memory import MemoryManager, MemoryBackend


class ArgusMemory:
    def __init__(self, memory_manager: Optional[MemoryManager] = None, project_path: Optional[Path] = None):
        self._memory = memory_manager
        self._project_path = os.path.normpath(str(project_path)) if project_path else None

    def set_project(self, project_path: Path) -> None:
        self._project_path = os.path.normpath(str(project_path))

    @property
    def available(self) -> bool:
        return self._memory is not None

    def retrieve_relevant(self, query: str, limit: int = 5) -> str:
        if not self._memory or not self._project_path:
            return ""
        try:
            return self._memory.retrieve_relevant_memory(query, self._project_path, limit=limit)
        except Exception:
            return ""

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self._memory or not self._project_path:
            return []
        try:
            return self._memory.search(query, project=self._project_path, limit=limit)
        except Exception:
            return []

    def add_observation(self, summary: str, details: str, entry_type: str = "observation", importance: float = 0.5) -> Optional[Dict[str, Any]]:
        if not self._memory or not self._project_path:
            return None
        try:
            return self._memory.store(entry_type, f"{summary}\n{details}", project=self._project_path, importance=importance)
        except Exception:
            return None

    def add_decision(self, decision: str, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self._memory or not self._project_path:
            return None
        try:
            return self._memory.store_decision(decision, project=self._project_path, context=context)
        except Exception:
            return None

    def add_lesson(self, lesson: str) -> Optional[Dict[str, Any]]:
        if not self._memory or not self._project_path:
            return None
        try:
            return self._memory.store_lesson(lesson, project=self._project_path)
        except Exception:
            return None

    def add_architecture(self, architecture: str) -> Optional[Dict[str, Any]]:
        if not self._memory or not self._project_path:
            return None
        try:
            return self._memory.store_project_architecture(architecture, project=self._project_path)
        except Exception:
            return None

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self._memory or not self._project_path:
            return []
        try:
            return self._memory.list(project=self._project_path, limit=limit)
        except Exception:
            return []
