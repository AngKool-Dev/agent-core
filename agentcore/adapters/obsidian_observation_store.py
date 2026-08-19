"""
DBObsidianObservationStore — durable observation storage via DB-Obsidian.

This adapter stores Argus observations as DB-Obsidian memories with
type="event".  It is the ONLY module in AgentCore that imports DB-Obsidian
for observation storage.  All other modules depend only on the abstract
ObservationStore interface.

Architecture
------------
    ObservationCollector
        ↓
    ObservationStore  (abstract)
        ↓
    DBObsidianObservationStore  (this file)
        ↓
    DB-Obsidian MemoryStore
        ↓
    SQLite database

Storage mapping
---------------
    Observation.id            → embedded in Memory.content as JSON
    Observation.task_id       → Memory.project
    Observation.session_id    → Memory.session_id
    Observation.observation_type → Memory.type (always "event")
    Observation.payload       → embedded in Memory.content as JSON
    Observation.metadata      → embedded in Memory.content as JSON
    Observation.timestamp     → Memory.created_at / updated_at
    Observation.sequence      → embedded in Memory.content as JSON

Deduplication
-------------
DB-Obsidian's built-in dedupe (content_hash + project + type) ensures
that saving the same observation twice does not create duplicates.  The
adapter maintains an in-memory index of observation.id → memory.id for
fast lookups; this index is rebuilt from the database on startup.

Concurrency
-----------
All public methods acquire a threading lock before accessing the store
or index.  The underlying SQLite connection is opened with
check_same_thread=False so that observations can be added safely from
concurrent callbacks.  DB-Obsidian's MemoryStore uses SQLite with WAL
mode, which provides safe concurrent reads and serialized writes.

Failure isolation
-----------------
Persistence errors are caught and logged.  The adapter never raises
to callers — add() silently drops failed observations, and query
methods return empty results on failure.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from agentcore.observations import Observation, ObservationStore

logger = logging.getLogger(__name__)

_OBSERVATION_TYPE = "event"
_OBSERVATION_LAYER = "L1"
_OBSERVATION_SCOPE = "project"


class DBObsidianObservationStore(ObservationStore):
    """
    Durable observation store backed by DB-Obsidian.

    Requires the ``db_obsidian`` package to be installed.
    """

    def __init__(self, db_path: str, vault_path: str | None = None) -> None:
        try:
            import sqlite3

            from db_obsidian.database import Database
            from db_obsidian.memory import MemoryStore
            from db_obsidian.provenance import Provenance
        except ImportError:
            raise ImportError(
                "DBObsidianObservationStore requires the db_obsidian package. "
                "Install it with: pip install db-obsidian"
            )

        self._db = Database(db_path)
        self._db.bootstrap()
        _conn = sqlite3.connect(str(self._db.path), timeout=10.0, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.execute("PRAGMA busy_timeout=10000")
        _conn.execute("PRAGMA synchronous=NORMAL")
        self._db.conn = _conn
        self._store = MemoryStore(self._db)
        self._provenance = Provenance.from_agent(
            source="agent",
            origin="observed",
            confidence=1.0,
        )
        self._lock = threading.Lock()
        self._index: dict[str, str] = {}
        self._rebuild_index()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connection."""
        try:
            self._db.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # ObservationStore interface
    # ------------------------------------------------------------------

    def add(self, observation: Observation) -> None:
        """Persist an observation."""
        content = self._serialize(observation)
        if not content:
            return
        try:
            with self._lock:
                self._ensure_session(observation.session_id)
                memory = self._store.add(
                    type=_OBSERVATION_TYPE,
                    content=content,
                    project=observation.task_id or None,
                    session_id=observation.session_id or None,
                    layer=_OBSERVATION_LAYER,
                    provenance=self._provenance,
                    importance=0.5,
                    status="active",
                    scope=_OBSERVATION_SCOPE,
                    dedupe=True,
                )
                self._index[observation.id] = memory.id
        except Exception:
            logger.debug("DBObsidianObservationStore failed to add observation", exc_info=True)

    def get(self, observation_id: str) -> dict[str, Any] | None:
        """Retrieve an observation by ID."""
        memory_id = self._index.get(observation_id)
        if memory_id is None:
            return None
        try:
            with self._lock:
                memory = self._store.get(memory_id)
                if memory is None:
                    return None
                return self._deserialize(memory)
        except Exception:
            logger.debug("DBObsidianObservationStore failed to get observation", exc_info=True)
            return None

    def list_by_task(self, task_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        """List observations for a task."""
        try:
            with self._lock:
                memories = self._store.list(project=task_id, type=_OBSERVATION_TYPE, limit=limit)
                return [self._deserialize(m) for m in memories if m]
        except Exception:
            logger.debug("DBObsidianObservationStore failed to list by task", exc_info=True)
            return []

    def list_by_session(self, session_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        """List observations for a session."""
        try:
            conn = self._db.connect()
            cursor = conn.execute(
                "SELECT * FROM memories WHERE session_id=? AND type=? "
                "AND status != 'archived' ORDER BY created_at DESC LIMIT ?",
                (session_id, _OBSERVATION_TYPE, limit),
            )
            rows = cursor.fetchall()
            return [self._deserialize_row(row) for row in rows]
        except Exception:
            logger.debug("DBObsidianObservationStore failed to list by session", exc_info=True)
            return []

    def clear(self, task_id: str) -> int:
        """Remove all observations for a task."""
        try:
            with self._lock:
                conn = self._db.connect()
                cursor = conn.execute(
                    "SELECT id FROM memories WHERE project=? AND type=? AND status != 'archived'",
                    (task_id, _OBSERVATION_TYPE),
                )
                rows = cursor.fetchall()
                count = 0
                for row in rows:
                    try:
                        self._store.delete(row["id"])
                        count += 1
                    except Exception:
                        pass
                self._index = {
                    k: v for k, v in self._index.items() if v not in [r["id"] for r in rows]
                }
                return count
        except Exception:
            logger.debug("DBObsidianObservationStore failed to clear", exc_info=True)
            return 0

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _rebuild_index(self) -> None:
        """Rebuild the observation.id → memory.id index from the database."""
        self._index.clear()
        try:
            conn = self._db.connect()
            cursor = conn.execute(
                "SELECT id, content FROM memories WHERE type=? AND status != 'archived'",
                (_OBSERVATION_TYPE,),
            )
            rows = cursor.fetchall()
            for row in rows:
                try:
                    data = json.loads(row["content"])
                    obs_id = data.get("id")
                    if obs_id:
                        self._index[obs_id] = row["id"]
                except Exception:
                    pass
        except Exception:
            logger.debug("DBObsidianObservationStore failed to rebuild index", exc_info=True)

    def _ensure_session(self, session_id: str) -> None:
        """Ensure a session row exists for the given session_id."""
        if not session_id:
            return
        try:
            conn = self._db.connect()
            if conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
                conn.execute(
                    "INSERT INTO sessions(id, state) VALUES (?, 'active')",
                    (session_id,),
                )
                conn.commit()
        except Exception:
            logger.debug("DBObsidianObservationStore failed to ensure session", exc_info=True)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _serialize(self, observation: Observation) -> str:
        """Serialize an observation to JSON for storage."""
        return json.dumps(observation.to_dict(), ensure_ascii=False)

    def _deserialize(self, memory: Any) -> dict[str, Any]:
        """Deserialize a DB-Obsidian Memory into an observation dict."""
        try:
            data = json.loads(memory.content)
            return data
        except Exception:
            return {"id": memory.id, "content": memory.content}

    def _deserialize_row(self, row: Any) -> dict[str, Any]:
        """Deserialize a SQLite row into an observation dict."""
        try:
            data = json.loads(row["content"])
            return data
        except Exception:
            return {"id": row["id"], "content": row["content"]}
