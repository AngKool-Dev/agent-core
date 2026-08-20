import os
from pathlib import Path
from typing import Any, List, Dict, Optional

from agentcore.memory import MemoryBackend, MemoryManager
from db_obsidian.database import Database
from db_obsidian.memory import MemoryStore, Memory
from db_obsidian.provenance import Provenance


class DBObsidianBackend(MemoryBackend):
    def __init__(self, db_path: str | Path, vault_path: str | Path | None = None):
        self.db_path = Path(db_path).expanduser()
        self.vault_path = Path(vault_path).expanduser() if vault_path else None
        self.db = Database(self.db_path)
        self.db.bootstrap()
        self._store = MemoryStore(self.db)

    def search(self, query: str, project: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            from db_obsidian.search import SearchEngine
            engine = SearchEngine(self.db)
            results = engine.search(query, project=project, limit=limit)
            return [self._memory_to_dict(m, score) for m, score in results]
        except Exception as e:
            return []

    def store(self, type: str, content: str, project: Optional[str] = None, importance: float = 0.5) -> Dict[str, Any]:
        mem = self._store.add(
            type=type,
            content=content,
            project=project,
            provenance=Provenance.from_agent(),
            importance=importance,
        )
        return self._memory_to_dict(mem)

    def update(self, memory_id: str, content: str) -> Dict[str, Any]:
        mem = self._store.update_content(memory_id, content)
        return self._memory_to_dict(mem)

    def list(self, project: Optional[str] = None, type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        memories = self._store.list(project=project, type=type, limit=limit)
        return [self._memory_to_dict(m) for m in memories]

    def _memory_to_dict(self, memory: Memory, score: float = 0.0) -> Dict[str, Any]:
        return {
            "id": memory.id,
            "type": memory.type,
            "content": memory.content,
            "project": memory.project,
            "session_id": memory.session_id,
            "layer": memory.layer,
            "importance": memory.importance,
            "status": memory.status,
            "scope": memory.scope,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "score": score,
            "source": memory.provenance.source,
            "confidence": memory.provenance.confidence,
            "origin": memory.provenance.origin,
        }

    def close(self) -> None:
        self.db.close()


def create_memory_manager(db_path: str | Path | None = None, vault_path: str | Path | None = None) -> MemoryManager:
    if db_path is None:
        db_path = Path.home() / ".agentcore" / "memory.db"
    if vault_path is None:
        vault_path = Path.home() / "ObsidianVault" / "agent-memory"

    backend = DBObsidianBackend(db_path, vault_path)
    return MemoryManager(backend)