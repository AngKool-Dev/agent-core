# Memory System

AgentCore's memory system extracts, stores, and retrieves memories from task
observations. The system is designed for deterministic operation and graceful
degradation.

## Architecture

```
AgentCore
   │
   ├── EventBus ──────────────► ObservationCollector ──► ObservationStore
   │                                          │
   │                                          ▼
   │                                  MemoryHarvester ──► MemoryBackend
   │                                         │
   │                                         ▼
   │                                  MemoryCandidate
   │                                         │
   │                                         ▼
   │                                  MemoryBackend
   │
   └── TaskPersistence ──► FilesystemPersistenceBackend
```

### Components

| Component | Responsibility |
|---|---|
| `ObservationCollector` | Collects observations from runtime events |
| `ObservationStore` | Persists observations (DB-Obsidian or in-memory) |
| `MemoryHarvester` | Extracts memory candidates from observations |
| `MemoryCandidate` | Structured candidate with deterministic ID |
| `MemoryBackend` | Stores `MemoryRecord` objects |
| `MemoryManager` | Orchestration layer; failure isolation |

## Memory Backend

Two backends are available:

| Backend | Class | Persistent | Dependencies |
|---|---|---|---|
| In-memory (default) | `InMemoryBackend` | No | None |
| DB-Obsidian | `DBObsidianBackend` | Yes | `pip install db-obsidian` |

If `db-obsidian` is not installed, AgentCore falls back to `InMemoryBackend`
automatically. This is handled in:

- `agentcore/cli/service.py` — `_try_dbobsidian_memory_backend()`
- `agentcore/cli/main.py` — runtime backend selection

## Memory Types

| Type | Description |
|---|---|
| `task` | Information about a specific task |
| `project` | Project-level facts (dependencies, structure) |
| `conversation` | Key conversation points |
| `decision` | Architectural or design decisions |
| `fact` | Verified facts about the codebase |
| `error` | Error patterns and their resolutions |
| `outcome` | Task completion outcomes |
| `learning` | General learnings from execution |

## Confidence Model

Memory confidence is **deterministic** in v0.1.0. It is assigned at harvest time
based on the source of the memory.

### Confidence Levels

| Level | Score | Meaning |
|---|---|---|
| `UNKNOWN` | 0.3 | Inferred from observation; no explicit claim by the model |
| `INFERRED` | 0.5 | Derived from task execution patterns |
| `CLAIMED` | 0.7 | Explicitly stated by the model in an observation |
| `VERIFIED` | 1.0 | Matches a verified tool outcome |

### Classification Logic

1. **VERIFIED (1.0)**: The memory's source observation contains a verified
   tool result (e.g., `grep` found a specific pattern, file read confirmed
   content). The harvester checks the observation's `metadata.verified` field.

2. **CLAIMED (0.7)**: The model explicitly stated a claim in its response
   (e.g., "The bug is in `src/handler.py`"). The harvester detects these via
   pattern matching on model output and marks `confidence_reason` accordingly.

3. **INFERRED (0.5)**: The memory was derived from task execution patterns,
   such as recurring error messages or tool call sequences.

4. **UNKNOWN (0.3)**: The memory was extracted from an observation but no
   confidence signal was available. This is the default for ambiguous cases.

The confidence value is stored as a float in `MemoryRecord` and the level label
as a `MemoryConfidence` enum value in the record's metadata.

## Deterministic Candidate IDs

Memory candidates are identified by a deterministic ID computed from:

```
SHA-256(content + project_path + memory_type)
```

This ensures:

- **Idempotency**: The same memory harvested from multiple observations maps to
  the same `MemoryRecord`. Re-harvesting does not create duplicates.
- **Deduplication**: DB-Obsidian backend delegates deduplication to the
  underlying database's primary key constraint on the candidate ID.
- **Cross-session consistency**: The same codebase context yields the same
  memory ID across different AgentCore sessions.

## Memory Harvesting Flow

```
Observation (from EventBus)
    │
    ▼
MemoryHarvester.observe()
    │
    ├── Extract content from observation payload
    ├── Classify memory type
    ├── Compute deterministic candidate ID
    ├── Assign confidence level
    │
    ▼
MemoryCandidate
    │
    ▼
MemoryManager.store_candidate()
    │
    ├── Check if candidate ID already exists
    ├── Update or insert MemoryRecord
    ├── Update confidence if higher
    │
    ▼
MemoryBackend.store()
```

## Memory Retrieval

### Search

```python
from agentcore import InMemoryBackend

backend = InMemoryBackend()
results = backend.search(
    query="dependency injection",
    project="/path/to/project",
    limit=20,
    min_confidence=0.5,
    memory_type="fact",
)
```

Search performs content matching across all stored memories. Results are sorted
by relevance and filtered by `min_confidence`.

### Get by ID

```python
memory = backend.get("mem-a1b2c3d4e5f6")
```

### List

```python
all_memories = backend.list(
    project="/path/to/project",
    type="fact",
    limit=50,
)
```

## Persistence Boundaries

| Component | Persistence | Backend |
|---|---|---|
| Task state | Filesystem (JSON) | `FilesystemPersistenceBackend` |
| Observations | Optional DB | `DBObsidianObservationStore` / `InMemoryObservationStore` |
| Memory | Optional DB | `DBObsidianBackend` / `InMemoryBackend` |
| Events | Ephemeral | `EventBus` (in-memory) |

AgentCore does **not** introduce its own database. When `db-obsidian` is
available, both observations and memory share the same SQLite database file
for consistency. When it is not available, both fall back to in-memory storage.

## Limitations

- Confidence classification is rule-based, not learned. There is no model
  fine-tuning of confidence in v0.1.0.
- `InMemoryBackend` does not persist across process restarts.
- Memory eviction/promotion is not implemented; `InMemoryBackend` stores all
  memories until process exit.
- Cross-project memory search is not supported in v0.1.0 (search is scoped
  per-project when using DB-Obsidian).
