"""
CLI query service layer for Phase 5F.

Assembles TaskRegistry, ObservationStore, and MemoryBackend from
configuration.  This is the only module that knows how to construct the
query stack from config / defaults.  The CLI command handlers depend only
on the abstractions exported here.

Architecture (read-only query path):

    CLI commands
        ↓
    QueryService
        ↓
    ├── TaskRegistry      (from persistence)
    ├── ObservationStore  (DBObsidianObservationStore or InMemoryObservationStore)
    └── MemoryBackend     (DBObsidianBackend or InMemoryBackend)
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from agentcore.config import AgentCoreConfig, ConfigLoader, user_data_dir
from agentcore.memory import MemoryBackend, MemoryManager
from agentcore.observations import InMemoryObservationStore, ObservationStore
from agentcore.persistence import (
    FilesystemPersistenceBackend,
    InMemoryEventStore,
    TaskPersistenceManager,
)
from agentcore.task_registry import TaskRegistry


@dataclass
class QueryService:
    """Assembled query components for CLI inspection."""

    task_registry: TaskRegistry
    persistence: TaskPersistenceManager
    observation_store: ObservationStore
    memory_backend: MemoryBackend
    memory_manager: MemoryManager
    data_dir: Path


def _try_dbobsidian_observation_store(db_path: str) -> ObservationStore | None:
    try:
        from agentcore.adapters.obsidian_observation_store import DBObsidianObservationStore

        store = DBObsidianObservationStore(db_path)
        return store
    except Exception:
        return None


def _try_dbobsidian_memory_backend(db_path: str) -> MemoryBackend | None:
    try:
        from agentcore.adapters.memory_dbobsidian import DBObsidianBackend

        return DBObsidianBackend(db_path)
    except Exception:
        return None


def create_query_service(
    config: AgentCoreConfig | None = None,
    data_dir: Path | None = None,
    projects: list[str] | None = None,
) -> QueryService:
    """Create a QueryService from config or defaults.

    Uses DB-Obsidian backends when available and db_path is configured.
    Falls back to in-memory backends otherwise.
    """
    if config is None:
        config = ConfigLoader.discover()

    if data_dir is None:
        data_dir = user_data_dir() / "argus"

    # --- Persistence (for tasks) ---
    tasks_dir = data_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    persistence_backend = FilesystemPersistenceBackend(base_path=tasks_dir)
    event_store = InMemoryEventStore()
    persistence = TaskPersistenceManager(backend=persistence_backend, event_store=event_store)

    # --- TaskRegistry (recover from persistence) ---
    registry = TaskRegistry(persistence=persistence)
    try:
        registry.recover_from_persistence(persistence)
    except Exception:
        pass

    # --- Memory backend ---
    db_path = config.memory_db_path if config.memory_db_path else str(data_dir / "memory.db")

    mem_backend = _try_dbobsidian_memory_backend(db_path)
    if mem_backend is None:
        from agentcore.memory import InMemoryBackend

        mem_backend = InMemoryBackend()

    memory_manager = MemoryManager(mem_backend)

    # --- Observation store ---
    obs_store = _try_dbobsidian_observation_store(db_path)
    if obs_store is None:
        obs_store = InMemoryObservationStore()

    return QueryService(
        task_registry=registry,
        persistence=persistence,
        observation_store=obs_store,
        memory_backend=mem_backend,
        memory_manager=memory_manager,
        data_dir=data_dir,
    )


def close_query_service(svc: QueryService) -> None:
    """Clean up resources held by a QueryService."""
    try:
        if hasattr(svc.observation_store, "close"):
            svc.observation_store.close()
    except Exception:
        pass
    try:
        if hasattr(svc.memory_backend, "close"):
            svc.memory_backend.close()
    except Exception:
        pass


def create_ephemeral_query_service() -> QueryService:
    """Create a QueryService backed by temporary files.

    Used by tests — does not touch the user's real data directory.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="argus-cli-test-"))
    config = AgentCoreConfig.defaults()
    config.memory_db_path = str(tmp_dir / "memory.db")

    tasks_dir = tmp_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    persistence_backend = FilesystemPersistenceBackend(base_path=tasks_dir)
    event_store = InMemoryEventStore()
    persistence = TaskPersistenceManager(backend=persistence_backend, event_store=event_store)
    registry = TaskRegistry(persistence=persistence)

    mem_backend = _try_dbobsidian_memory_backend(str(tmp_dir / "memory.db"))
    if mem_backend is None:
        from agentcore.memory import InMemoryBackend

        mem_backend = InMemoryBackend()
    memory_manager = MemoryManager(mem_backend)

    obs_store = _try_dbobsidian_observation_store(str(tmp_dir / "memory.db"))
    if obs_store is None:
        obs_store = InMemoryObservationStore()

    return QueryService(
        task_registry=registry,
        persistence=persistence,
        observation_store=obs_store,
        memory_backend=mem_backend,
        memory_manager=memory_manager,
        data_dir=tmp_dir,
    )
