from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from db_obsidian.database import Database
from db_obsidian.memory import Memory, MemoryStore
from db_obsidian.provenance import Provenance

from agentcore.memory import MemoryBackend, MemoryManager


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class DBObsidianBackend(MemoryBackend):
    def __init__(self, db_path: str | Path, vault_path: str | Path | None = None):
        self.db_path = Path(db_path).expanduser()
        self.vault_path = Path(vault_path).expanduser() if vault_path else None
        self.db = Database(self.db_path)
        self.db.bootstrap()
        self._store = MemoryStore(self.db)

    def search(
        self,
        query: str,
        project: str | None = None,
        limit: int = 20,
        min_confidence: float | None = None,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            from db_obsidian.search import SearchEngine

            engine = SearchEngine(self.db)
            types = [memory_type] if memory_type else None
            results = engine.search(query, project=project, limit=limit, types=types)
            dicts = [self._memory_to_dict(m, score) for m, score in results]
            if min_confidence is not None:
                dicts = [d for d in dicts if d.get("confidence", 0.0) >= min_confidence]
            return dicts
        except Exception:
            return []

    def get(self, memory_id: str) -> dict[str, Any] | None:
        try:
            mem = self._store.get(memory_id)
            if mem is None:
                return None
            return self._memory_to_dict(mem)
        except Exception:
            return None

    def store(
        self,
        type: str,
        content: str,
        project: str | None = None,
        importance: float = 0.5,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        mem = self._store.add(
            type=type,
            content=content,
            project=project,
            provenance=Provenance.from_agent(),
            importance=importance,
            confidence=confidence,
        )
        return self._memory_to_dict(mem)

    def update(self, memory_id: str, content: str) -> dict[str, Any]:
        mem = self._store.update_content(memory_id, content)
        return self._memory_to_dict(mem)

    def update_confidence(
        self, memory_id: str, confidence: float, reason: str = ""
    ) -> dict[str, Any] | None:
        conn = self.db.connect()
        with conn:
            cur = conn.execute(
                "UPDATE memories SET confidence=?, updated_at=? WHERE id=?",
                (confidence, _now_iso(), memory_id),
            )
            if cur.rowcount == 0:
                return None
        mem = self._store.get(memory_id)
        return self._memory_to_dict(mem)

    def list(
        self, project: str | None = None, type: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        memories = self._store.list(project=project, type=type, limit=limit)
        return [self._memory_to_dict(m) for m in memories]

    def _memory_to_dict(self, memory: Memory, score: float = 0.0) -> dict[str, Any]:
        if memory is None:
            return {}
        result = {
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
        if memory.provenance.source_id:
            result["source_id"] = memory.provenance.source_id
        if memory.provenance.created_by:
            result["created_by"] = memory.provenance.created_by
        return result

    def close(self) -> None:
        self.db.close()


def create_memory_manager(
    db_path: str | Path | None = None, vault_path: str | Path | None = None
) -> MemoryManager:
    if db_path is None:
        from agentcore.config import user_data_dir

        db_path = user_data_dir() / "memory.db"
    if vault_path is None:
        from agentcore.config import user_data_dir

        vault_path = user_data_dir() / "agent-memory"

    backend = DBObsidianBackend(db_path, vault_path)
    return MemoryManager(backend)
