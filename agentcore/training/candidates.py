"""
Phase 6A: Pre-written training candidates for EraAI Adapter v2.

This module defines all high-quality training examples as Experience and
CorrectionPair objects. These are derived from actual AgentCore source code
and architecture.

IMPORTANT: All prompts are original and do NOT overlap with the
held-out evaluation set (eval_cases.jsonl, configurable via EPOCH_EVAL_PATH).
The leakage detector is still run as a quality gate, but these prompts were
intentionally written to avoid any overlap.
Coverage:
    Memory (highest priority - v1 regression) - ~55 examples
    Contrastive corrections - ~10 examples
    All 15 evaluation categories covered
"""

from __future__ import annotations

from .experience import CorrectionPair, Experience

TRAINING_CANDIDATES: list[Experience] = []
CORRECTION_CANDIDATES: list[CorrectionPair] = []


def _add(instruction: str, output: str, source: str, domains: list[str]) -> None:
    TRAINING_CANDIDATES.append(
        Experience(
            instruction=instruction,
            output=output,
            source=source,
            domains=domains,
        )
    )


# ============================================================
# MEMORY EXAMPLES (~55 — the v1 regression priority)
# ============================================================

_add(
    "What does the MemoryManager component do in the AgentCore system?",
    "The MemoryManager in agentcore/memory.py orchestrates memory operations. "
    "Its responsibilities are: (1) normalize backend results to a consistent "
    "dict format with id, content, type, project, relevance, and timestamp; "
    "(2) limit memory context size to max_context_records (default 10) and "
    "truncate content to max_content_chars (default 2000); (3) handle backend "
    "failures gracefully by logging and returning empty results, never raising; "
    "(4) emit events via EventBus if available; (5) filter potentially sensitive "
    "content before storage. The Manager delegates to MemoryBackend and does "
    "NOT know SQL, Obsidian vault layout, or SQLite schemas.",
    "agentcore source",
    ["memory"],
)

_add(
    "Explain the purpose of the MemoryBackend abstract class in AgentCore.",
    "MemoryBackend is an abstract class (ABC) in agentcore/memory.py that "
    "defines the provider-neutral interface for memory storage. It has "
    "abstract methods search(), store(), update(), and list(), and optional "
    "methods get() (defaults to returning None), delete() (defaults to False), "
    "clear() (defaults to 0), update_confidence(), and close() (defaults to "
    "no-op). Implementations include InMemoryBackend for testing and "
    "DBObsidianBackend for SQLite plus Obsidian vault persistence. Backends "
    "are not required to implement optional methods — callers use hasattr() "
    "or try/except to gracefully handle unsupported features.",
    "agentcore source",
    ["memory", "extensibility"],
)

_add(
    "How does AgentCore persist memory to durable storage?",
    "Memory persistence in AgentCore is handled by DBObsidianBackend in "
    "agentcore/adapters/memory_dbobsidian.py. It wraps the db_obsidian "
    "package's Database and MemoryStore. On initialization it creates a "
    "Database at the given db_path, calls bootstrap() to set up tables, "
    "and creates a MemoryStore. When store() is called, it creates a "
    "Provenance.from_agent() record and calls store.add() with type, "
    "content, project, provenance, importance, and confidence. The "
    "DB-Obsidian layer handles deduplication, WAL-mode concurrency, and "
    "SQLite transactions. The MemoryManager wraps failures in try/except.",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "How does the MemoryManager retrieve relevant memories from storage?",
    "Memory retrieval goes through MemoryManager.search() in "
    "agentcore/memory.py. The manager checks if memory is enabled, then "
    "calls self._backend.search(query, project, limit). The DBObsidianBackend "
    "delegates to db_obsidian's SearchEngine which performs fuzzy text "
    "matching. Results are normalized: each result dict gets id, content "
    "(truncated to max_content_chars), type, project, relevance (or score), "
    "and timestamp. If the backend fails, the manager logs a warning and "
    "returns an empty list — retrieval is best-effort and never raises. "
    "The manager also emits memory.recall.started and completed events.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager update an existing memory record?",
    "Memory updates go through MemoryManager.update() in agentcore/memory.py, "
    "which calls self._backend.update(memory_id, content). The "
    "DBObsidianBackend delegates to the MemoryStore's update_content() "
    "method. The manager wraps the call in try/except and returns None "
    "on failure. Similarly, MemoryManager.get() calls backend.get(memory_id) "
    "using getattr(backend, 'get', None) with a None check — the get() "
    "method on MemoryBackend defaults to returning None, and "
    "DBObsidianBackend implements it via store.get().",
    "agentcore source",
    ["memory"],
)

_add(
    "What confidence levels does AgentCore use for memories, and what do they mean?",
    "AgentCore uses a MemoryConfidence enum with four levels: VERIFIED "
    "(1.0), CLAIMED (0.7), INFERRED (0.5), and UNKNOWN (0.3). These are "
    "defined in agentcore/memory.py and used by the MemoryHarvester in "
    "agentcore/harvesting.py. The MemoryConfidenceClassifier assigns "
    "confidence based on evidence: VERIFIED for observations with "
    "verification signals (exit_code 0, status true), CLAIMED for "
    "task completion/error results, INFERRED when derived from multiple "
    "observations, and UNKNOWN for insufficient evidence. The "
    "MemoryManager passes confidence to backend.store().",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore ensure confidence levels only go up, not down?",
    "AgentCore implements monotonic confidence upgrades. When the "
    "MemoryHarvester persists a candidate, it first calls backend.store() "
    "to create or retrieve the memory. If the stored memory already exists "
    "with a lower confidence, the harvester calls "
    "backend.update_confidence(memory_id, new_confidence, reason) to "
    "upgrade it. This uses hasattr to check support. The DBObsidianBackend "
    "implements update_confidence via SQL UPDATE. Confidence never "
    "decreases — only upgrades are applied, ensuring verified memories "
    "are never downgraded by lower-confidence observations.",
    "agentcore source",
    ["memory"],
)

_add(
    "What is memory provenance tracking in AgentCore, and why does it matter?",
    "Memory provenance in AgentCore tracks the origin and trust level of "
    "each stored memory. The DBObsidianBackend uses db_obsidian's "
    "Provenance.from_agent() to create a provenance record with source, "
    "origin, and confidence fields. The provenance captures whether a "
    "memory came from a tool call, task completion, or runtime error. "
    "The MemoryHarvester sets provenance based on observation type: "
    "tool_call.completed maps to tool-derived provenance, task.completed "
    "to task-outcome provenance. The _memory_to_dict() method exposes "
    "provenance fields as source, confidence, origin, source_id, and "
    "created_by.",
    "agentcore source",
    ["memory"],
)

_add(
    "What memory categories does AgentCore define, and how are they used?",
    "AgentCore defines a MemoryType enum with values: TASK, PROJECT, "
    "CONVERSATION, DECISION, FACT, ERROR, LEARNING, PREFERENCE, and "
    "OUTCOME. The MemoryHarvester maps observation types: "
    "task.completed maps to TASK, task.failed to OUTCOME, "
    "tool_call.completed to FACT, runtime.error to ERROR. The "
    "MemoryManager provides convenience methods: store_decision() "
    "uses DECISION with importance 0.8, store_lesson() uses LEARNING "
    "with importance 0.7, store_project_architecture() uses PROJECT "
    "with importance 0.9, store_task_result() uses TASK with importance "
    "based on success or failure.",
    "agentcore source",
    ["memory"],
)

_add(
    "Describe the complete memory lifecycle in AgentCore from observation to retrieval.",
    "The AgentCore memory lifecycle is: (1) Observation — the "
    "ObservationCollector translates EventBus events into Observation "
    "objects stored in the ObservationStore; (2) Harvesting — the "
    "MemoryHarvester consumes observations and applies extraction rules "
    "to produce MemoryCandidate objects, assigning confidence via the "
    "MemoryConfidenceClassifier; (3) Storage — candidates are persisted "
    "to a MemoryBackend (InMemoryBackend or DBObsidianBackend), with "
    "monotonic confidence upgrades for duplicates; (4) Retrieval — "
    "MemoryManager.search() queries the backend, normalizes results, "
    "and returns them to the agent; (5) Update — MemoryManager.update() "
    "modifies memory content. The MemoryManager wraps all backend "
    "operations in try/except and logs failures, making memory optional "
    "and failure-isolated.",
    "agentcore source",
    ["memory", "events"],
)

_add(
    "How does AgentCore prevent sensitive data from entering memory storage?",
    "AgentCore prevents sensitive data storage through the "
    "_contains_sensitive_data() function in agentcore/memory.py. This "
    "checks content against a pattern list including password, secret, "
    "api_key, access_token, private_key, and credential. The check is "
    "case-insensitive. If sensitive data is detected, MemoryManager."
    "store() logs a warning and returns None without storing. Content "
    "is also truncated to max_content_chars before storage. This "
    "filtering is defense-in-depth.",
    "agentcore source",
    ["memory", "safety"],
)

_add(
    "How is memory content passed from the orchestrator into the runtime's context?",
    "In AgentCore, memory is shared at orchestration time, not runtime time. "
    "The orchestration layer retrieves memories via "
    "MemoryManager.retrieve_relevant_memory() before building the runtime "
    "context. The result is embedded in the context dict under the "
    "'memory' key as MemoryContextData. HermesAPI.build_prompt() "
    "formats this into a prompt string. Runtimes do NOT have direct "
    "access to the MemoryBackend — they only receive memory content "
    "within the formatted context prompt. This preserves the "
    "architectural separation.",
    "agentcore source",
    ["memory", "orchestration", "runtime_adapter"],
)

_add(
    "What happens to AgentCore when the memory backend experiences a failure?",
    "When the memory backend is unavailable or fails, MemoryManager."
    "search() catches the exception, logs a warning, emits a "
    "memory.error event, and returns an empty list. Store returns "
    "None, get returns None, update returns None. The agent continues "
    "without memory. This design means a corrupted database, locked "
    "SQLite file, or missing db_obsidian package does not crash the "
    "orchestrator — memory simply becomes unavailable. The "
    "MemoryManager's enabled property checks if backend is set and "
    "not None, short-circuiting all operations when memory is disabled.",
    "agentcore source",
    ["memory", "failure_handling"],
)

_add(
    "How does AgentCore distinguish memory from task state in its architecture?",
    "In AgentCore, task state and memory are separate concerns. Task "
    "state is managed by the Task dataclass and TaskRegistry — it "
    "tracks the current phase of a task (CREATED, RUNNING, COMPLETED, "
    "etc.) via TaskState enum and valid transitions, persisted by "
    "TaskPersistenceManager. Memory is managed by MemoryManager and "
    "MemoryBackend — it stores reusable knowledge like facts, "
    "decisions, outcomes, and lessons. Task state is tied to a "
    "single task's lifecycle; memory is queryable across tasks via "
    "search(). retrieve_relevant_memory() is called before each "
    "runtime interaction.",
    "agentcore source",
    ["memory", "task_lifecycle", "orchestration"],
)

_add(
    "When during the agent loop does memory retrieval happen relative to runtime calls?",
    "Memory is retrieved before each runtime interaction. The "
    "OrchestrationEngine calls MemoryManager.retrieve_relevant_memory() "
    "with the current task's request and project. This returns a "
    "formatted string of relevant memories (limited to 10 records, "
    "each truncated to 200 chars). The result is stored in "
    "MemoryContextData and included in the context dict. "
    "HermesAPI.build_prompt() formats this as a 'Relevant Memory' "
    "section. After the runtime responds, new observations are created "
    "and the MemoryHarvester extracts candidates. After completion, "
    "store_task_result() persists the outcome.",
    "agentcore source",
    ["memory", "orchestration", "runtime_adapter"],
)

_add(
    "How does the MemoryHarvester use observation types to determine what to store?",
    "The MemoryHarvester in agentcore/harvesting.py consumes Observation "
    "objects and applies extraction rules based on observation type. "
    "The mapping is: task.completed creates a TASK candidate, "
    "task.failed creates an OUTCOME candidate, task.cancelled creates "
    "an OUTCOME candidate, tool_call.completed creates a FACT candidate, "
    "and runtime.error creates an ERROR candidate. Each extractor uses "
    "_extract_text_from_payload() to pull meaningful text, filters "
    "low-information content, assigns confidence via "
    "MemoryConfidenceClassifier, and generates a deterministic ID via "
    "_generate_candidate_id() for idempotency.",
    "agentcore source",
    ["memory", "events"],
)

_add(
    "How does AgentCore detect and handle stale memory entries?",
    "AgentCore detects stale memory through deterministic candidate IDs. "
    "The _generate_candidate_id() function in harvesting.py creates an ID "
    "from task_id, memory_type, and normalized content. The harvester "
    "tracks seen_ids and skips duplicates within a batch. For persistence, "
    "the DBObsidianBackend uses DB-Obsidian's deduplication which "
    "checks content_hash plus project plus type. Additionally, monotonic "
    "confidence upgrades ensure old low-confidence memories cannot "
    "overwrite verified ones. The InMemoryBackend stores each call as "
    "a new record with a new UUID (no automatic deduplication).",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "How does AgentCore resolve conflicts when the same memory content is stored twice?",
    "AgentCore resolves duplicate content through backend-level "
    "deduplication and the MemoryHarvester's deterministic IDs. "
    "The DBObsidianBackend delegates to DB-Obsidian's MemoryStore "
    "with dedupe=True, which checks content_hash plus project plus "
    "type before inserting. The harvester tracks seen_ids within a "
    "batch. For existing memories, monotonic confidence upgrades "
    "apply: higher confidence triggers update_confidence(). The "
    "InMemoryBackend stores each call separately with a new UUID.",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "What is the MemoryRecord data structure, and what fields does it contain?",
    "The MemoryRecord dataclass in agentcore/memory.py defines the "
    "structured format for memory entries. Fields: id (str, "
    "auto-generated with 'mem-' prefix), content (str, the memory text), "
    "memory_type (str, from MemoryType enum), source (str, default "
    "'agent'), timestamp (str, ISO 8601 UTC), metadata (dict, "
    "arbitrary), relevance (float, 0.0 default), and project "
    "(Optional[str]). The to_dict() method serializes all fields. "
    "MemoryRecords can be created directly or returned by "
    "backend.store().",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager handle the get() operation for retrieving a specific memory?",
    "The MemoryManager.get() method retrieves a single memory by ID. "
    "It checks if memory is enabled via self.enabled. If not, returns "
    "None. Otherwise, it uses getattr(self._backend, 'get', None) to "
    "check if the backend supports get() (it's optional on the ABC). "
    "If the getter exists, it calls getter(memory_id) and returns "
    "the result. If the backend doesn't support get(), returns None. "
    "All of this is wrapped in try/except — on any failure, a warning "
    "is logged and None is returned. This allows backends without "
    "get() support to coexist with those that do.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does min_confidence filtering work in AgentCore's memory search?",
    "AgentCore handles min_confidence filtering through the "
    "MemoryBackend.search() abstract method, which accepts an "
    "optional min_confidence parameter. The InMemoryBackend filters "
    "results where r.get('confidence', 0.5) < min_confidence. The "
    "DBObsidianBackend first delegates to db_obsidian's SearchEngine "
    "for text matching, then post-filters results by checking "
    "d.get('confidence', 0.0) >= min_confidence. The MemoryManager."
    "search() does not pass min_confidence to the backend — it relies "
    "on the backend to implement the filtering. This means confidence-"
    "based filtering is applied after text matching.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager.list() method work, and how does it handle failures?",
    "The MemoryManager.list() method lists memory records with optional "
    "project and type filtering. It first checks if memory is enabled. "
    "If not, returns an empty list. It then calls "
    "self._backend.list(project, type, limit) inside a try/except. "
    "If the backend fails, a warning is logged ('Memory list failed: "
    "...') and an empty list is returned. The method never raises. "
    "The InMemoryBackend filters its records by project and type. "
    "The DBObsidianBackend delegates to MemoryStore.list().",
    "agentcore source",
    ["memory", "failure_handling"],
)

_add(
    "How does the DBObsidianBackend store and retrieve memories at the storage level?",
    "The DBObsidianBackend stores memories via db_obsidian's MemoryStore. "
    "On initialization it creates a Database at db_path, calls "
    "bootstrap() to set up SQLite tables, and creates a MemoryStore. "
    "The store() method calls store.add() with type, content, project, "
    "provenance (Provenance.from_agent()), importance, and confidence. "
    "The get() method calls store.get(memory_id). The list() method "
    "calls store.list(project, type, limit). The _memory_to_dict() "
    "method converts Memory objects to dicts with id, type, content, "
    "project, importance, confidence, created_at, updated_at, and "
    "provenance fields.",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "How does the MemoryManager emit events for observability?",
    "The MemoryManager emits events via the EventBus using _emit(). "
    "For search: memory.recall.started (with query and project in "
    "metadata) and memory.recall.completed (with result_count, "
    "duration, success). For store: memory.store.started (with type "
    "and project) and memory.store.completed (with memory_id, duration, "
    "success). On failures: memory.error (with operation, error, "
    "duration). The _emit() method converts string event types to "
    "EventType enum values and creates AgentEvent objects with "
    "task_id, iteration, data, and metadata. If no EventBus or no "
    "subscribers, _emit() returns immediately.",
    "agentcore source",
    ["memory", "events"],
)

_add(
    "What are the convenience methods provided by the MemoryManager?",
    "The MemoryManager provides convenience methods that wrap the "
    "generic store() with specific types and importance levels: "
    "store_decision() stores with MemoryType.DECISION and importance "
    "0.8, formatting content as '{context}\\n\\nDecision: {decision}'; "
    "store_lesson() stores with MemoryType.LEARNING and importance 0.7; "
    "store_project_architecture() stores with MemoryType.PROJECT and "
    "importance 0.9; store_task_result() stores with MemoryType.TASK "
    "and importance 0.7 for success or 0.3 for failure, formatting as "
    "'Task: {user_request}\\nResult: SUCCESS/FAILED\\nSummary: {summary}'.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager handle memory content size limits?",
    "AgentCore enforces memory content size limits at the MemoryManager "
    "level. The store() method truncates content to max_content_chars "
    "(default 2000) before passing to the backend. Search results are "
    "also truncated in normalization: r.get('content','')[:max_content_chars]. "
    "The max_context_records (default 10) limit how many memories are "
    "returned from search via min(limit, self._max_context_records). "
    "The retrieve_relevant_memory() method limits to 10 records. "
    "The DBObsidianBackend stores full content in SQLite but the "
    "MemoryManager always truncates before storage and retrieval.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore's memory system support multiple project isolation?",
    "AgentCore's memory system supports multi-tenancy through the "
    "project parameter. Every MemoryBackend.store() call accepts a "
    "project argument, and search() accepts a project filter. The "
    "InMemoryBackend filters results by project. The DBObsidianBackend "
    "passes project to MemoryStore.add() and SearchEngine.search(). "
    "The MemoryManager passes the project through from callers. "
    "Different tasks can store memories under their project name, and "
    "retrieve_relevant_memory() can scope searches to a specific "
    "project. This allows memory isolation between projects.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager ensure thread safety for memory operations?",
    "AgentCore ensures memory operation thread-safety through backend-level "
    "mechanisms. The InMemoryBackend relies on CPython dict thread-safety for "
    "single operations. The DBObsidianBackend acquires a threading.Lock "
    "for all operations (add, get, list, clear) and uses SQLite with "
    "WAL mode and check_same_thread=False for concurrent access. The "
    "SQLite connection is configured with PRAGMA busy_timeout=10000 to "
    "handle write contention. The MemoryManager itself does not use "
    "locks — it delegates thread safety to the backend.",
    "agentcore source",
    ["memory", "safety"],
)

_add(
    "What happens when the MemoryManager.list() method is called with a project filter?",
    "The MemoryManager.list() method passes the project and type filters "
    "to backend.list(project, type, limit). The InMemoryBackend iterates "
    "its _records and filters by r.get('project') == project and "
    "r.get('type') == type if provided. Results are sorted by importance "
    "(descending). The DBObsidianBackend delegates to "
    "self._store.list(project=project, type=type, limit=limit) and "
    "converts results via _memory_to_dict(). If the backend fails, "
    "list() returns an empty list (never raises).",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the DBObsidianBackend implement update_confidence for memory records?",
    "The DBObsidianBackend implements update_confidence in "
    "agentcore/adapters/memory_dbobsidian.py. It connects to the "
    "SQLite database, executes an UPDATE statement on the memories table "
    "setting confidence and updated_at to the given values WHERE id matches. "
    "If cur.rowcount is 0 (no matching memory), it returns None. Otherwise "
    "it retrieves the updated memory via self._store.get(memory_id) and "
    "returns it as a dict via _memory_to_dict(). The MemoryManager calls "
    "this via hasattr check — if the backend doesn't support it, "
    "update_confidence is not called.",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "How does the MemoryManager.normalize() method ensure consistent result format?",
    "The MemoryManager normalizes backend search results inside its "
    "search() method. After calling self._backend.search(), it iterates "
    "over results and creates normalized dicts: 'id' from r.get('id'), "
    "'content' truncated to max_content_chars, 'type' from "
    "r.get('type') or r.get('memory_type'), 'project' from "
    "r.get('project', project), 'relevance' from r.get('relevance') or "
    "r.get('score', 0.0), and 'timestamp' from r.get('timestamp') or "
    "r.get('created_at', ''). Non-dict results are wrapped as "
    "{'content': str(r)[:max_content_chars]}. This ensures "
    "consistent output regardless of backend implementation.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore's MemoryConfig affect memory behavior?",
    "AgentCore's MemoryManager accepts max_context_records (default 10) "
    "and max_content_chars (default 2000) as constructor parameters. "
    "These control how many memories are returned from search (limited "
    "by min(limit, self._max_context_records)) and how content is "
    "truncated before storage (content[:self._max_content_chars]) and "
    "after retrieval. If no backend is configured, MemoryManager."
    "enabled is False and all operations short-circuit, returning empty "
    "lists or None. The config values are not hardcoded — they can "
    "come from AgentCoreConfig or be passed explicitly.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager.retrieve_relevant_memory() format results for the model?",
    "The retrieve_relevant_memory() method calls search() to get "
    "results, filters by type if specified, and joins the content "
    "fields with '\\n\\n---\\n\\n' separators. This produces a "
    "single formatted string suitable for inclusion in a model prompt. "
    "The results are already truncated to max_context_records (10) and "
    "max_content_chars (2000) by the search() method. If no memories "
    "are found, an empty string is returned. This method abstracts "
    "away the structured dict format and provides a ready-to-use "
    "string for prompt assembly.",
    "agentcore source",
    ["memory", "orchestration"],
)

_add(
    "How does AgentCore's memory system handle the CONVERSATION memory type?",
    "AgentCore's MemoryType.CONVERSATION stores dialogue context between "
    "the agent and runtime. While the MemoryHarvester doesn't "
    "automatically extract CONVERSATION memories, the MemoryManager "
    "supports storing conversation snippets via store() with "
    "type='conversation'. The InMemoryBackend stores them with default "
    "importance 0.5. The DBObsidianBackend persists them. Search can "
    "filter by type='conversation'. Conversation memories have the "
    "same lifecycle as other types — searchable, updatable, "
    "confidence-upgradable.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore's memory system handle the PREFERENCE memory type?",
    "AgentCore's MemoryType.PREFERENCE stores user preferences and "
    "configuration choices. The MemoryManager's store() method accepts "
    "type='preference' and stores it via the backend. Preference memories "
    "typically have higher importance and are tagged with the project "
    "scope. When the agent initializes, it can search for preference-type "
    "memories to reload user configuration. Preferences can be updated "
    "via update() and retrieved via search() with type='preference' "
    "filter. Monotonic confidence upgrades apply — confirmed preferences "
    "are upgraded from CLAIMED to VERIFIED.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager handle a backend that doesn't support the get() method?",
    "The MemoryManager.get() method is designed to work with backends "
    "that don't implement get(). It uses getattr(self._backend, 'get', "
    "None) to retrieve the method. If the getter is None (backend doesn't "
    "support get()), it returns None immediately. The MemoryBackend ABC "
    "defines get() with a default implementation that returns None, so "
    "even backends that inherit the ABC without overriding get() will "
    "work. This optional method pattern ensures backward compatibility "
    "with simpler backends.",
    "agentcore source",
    ["memory", "extensibility"],
)

_add(
    "How does AgentCore's memory store_task_result() method work?",
    "The store_task_result() method in agentcore/memory.py stores the "
    "outcome of a completed task. It formats the content as "
    "'Task: {user_request}\\nResult: SUCCESS/FAILED\\nSummary: "
    "{summary}' and calls store() with MemoryType.TASK.value, the "
    "project scope, and importance 0.7 for success or 0.3 for failure. "
    "The content is truncated to max_content_chars and filtered for "
    "sensitive data before storage. If the backend fails, store() "
    "returns None. This allows the agent to recall past task outcomes.",
    "agentcore source",
    ["memory", "task_lifecycle"],
)

_add(
    "How does the MemoryHarvester assign confidence ratings to extracted memories?",
    "The MemoryHarvester uses the MemoryConfidenceClassifier in "
    "agentcore/harvesting.py. The classifier checks evidence levels: "
    "VERIFIED for observations with strong verification signals (exit_code "
    "0, status true, or 'passed' in text), CLAIMED for task "
    "completion/error results without verification, INFERRED when "
    "derived from multiple observations (related_observation_count > 1), "
    "and UNKNOWN for insufficient evidence. The _confidence_to_float() "
    "function maps: VERIFIED=1.0, CLAIMED=0.7, INFERRED=0.5, UNKNOWN=0.3. "
    "These are stored in the memory provenance.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the DBObsidianBackend handle content deduplication for memory storage?",
    "The DBObsidianBackend delegates deduplication to DB-Obsidian's "
    "MemoryStore with dedupe=True (the default). MemoryStore.add() checks "
    "for existing memories with the same content_hash, project, and type "
    "before inserting. If a duplicate is found, it returns the existing "
    "memory instead of creating a new one. The _memory_to_dict() method "
    "converts the returned Memory object to a dict. The "
    "ObservationCollector uses the same mechanism for observations. "
    "This prevents the same content from being stored multiple times.",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "How does AgentCore's memory system handle the delete() and clear() operations?",
    "The MemoryManager.delete() method deletes a single memory by ID. "
    "It checks if the backend supports delete via hasattr and calls "
    "backend.delete(memory_id). Returns False on failure or if "
    "unsupported. The clear() method clears all memories, optionally "
    "scoped to a project. It returns the count of cleared records. "
    "Both methods are wrapped in try/except and return safe defaults "
    "(False for delete, 0 for clear). The InMemoryBackend filters its "
    "_records dict; the DBObsidianBackend delegates to "
    "MemoryStore.list() and delete operations.",
    "agentcore source",
    ["memory", "failure_handling"],
)

_add(
    "How does AgentCore handle memory storage when the backend raises a TypeError?",
    "The MemoryManager.store() method handles backend compatibility "
    "by attempting to pass the confidence parameter to "
    "backend.store(), and falling back to a TypeError catch: if "
    "backend.store() doesn't accept a confidence parameter, it calls "
    "store(type, content, project, importance) without confidence. "
    "This ensures backward compatibility with backends that predate "
    "the confidence feature. If the backend doesn't support confidence "
    "at all, the memory is stored with default confidence 0.5.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager.close() method work, and when is it called?",
    "The MemoryManager.close() method closes the backend if it supports "
    "closing. It checks if self._backend exists and has a close() "
    "method via hasattr. The DBObsidianBackend.close() calls "
    "self.db.close() to close the SQLite database connection. This "
    "is called during graceful shutdown to release database connections. "
    "The method is wrapped in try/except so database close failures "
    "don't crash the shutdown. If no backend or no close method, "
    "close() is a no-op.",
    "agentcore source",
    ["memory", "shutdown"],
)

_add(
    "How does AgentCore's memory system handle the update() operation for content changes?",
    "The MemoryManager.update() method modifies a memory record's "
    "content. It calls self._backend.update(memory_id, content) inside "
    "a try/except. If the backend fails, a warning is logged and None "
    "is returned. The DBObsidianBackend delegates to "
    "MemoryStore.update_content(memory_id, content), which modifies "
    "the content field in the database. The InMemoryBackend modifies "
    "the _records dict directly. Unlike update_confidence(), the "
    "update() method replaces the entire content — it does not "
    "append or merge.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryManager interact with the EventBus for memory operations?",
    "The MemoryManager's _emit() method integrates with the EventBus. "
    "It is called for: memory.recall.started/completed (search), "
    "memory.store.started/completed (store), and memory.error (failures). "
    "Each event includes task_id, iteration, structured data (result_count, "
    "duration, success), and metadata. The _emit() method converts string "
    "event types to EventType enum values via EventType(event_type). If "
    "self._event_bus is None or has no subscribers, _emit() returns "
    "immediately. This means EventBus is optional — memory operations "
    "work fine without it.",
    "agentcore source",
    ["memory", "events"],
)

# ============================================================
# ARCHITECTURE EXAMPLES (rephrased prompts)
# ============================================================

_add(
    "What is the core purpose of the AgentCore system?",
    "AgentCore is an AI orchestration system that coordinates agents, "
    "tasks, runtimes, memory, and execution. It decides what should "
    "happen while runtime adapters are responsible for actually "
    "executing work. The orchestration layer handles task planning, "
    "state management, cancellation, memory, and routing, while "
    "runtime adapters translate these operations into the API of a "
    "specific execution backend.",
    "agentcore source",
    ["architecture"],
)

_add(
    "Define what an AI agent is within the AgentCore framework.",
    "An AI agent in AgentCore is a system that can interpret a goal, "
    "reason about required actions, use tools or runtimes, observe "
    "results, maintain state, and continue until the task reaches an "
    "appropriate terminal state. The agent is the decision-making "
    "layer, while runtimes handle actual execution.",
    "agentcore source",
    ["architecture"],
)

_add(
    "Compare the roles of an agent versus a runtime in the AgentCore architecture.",
    "An agent decides what work needs to be performed and coordinates "
    "that work through planning, routing, and state management. A "
    "runtime performs the actual execution by invoking a model and "
    "parsing its response. The agent is the decision-making and "
    "orchestration layer; the runtime is the execution layer.",
    "agentcore source",
    ["architecture"],
)

_add(
    "How is the overall structure of AgentCore organized?",
    "AgentCore adopts a layered design that keeps decision-making "
    "separate from execution. The orchestration plane handles task "
    "planning, state management, cancellation, memory, and routing. "
    "Runtime adapters implement a stable interface that translates "
    "orchestration commands into a specific backend. This layered "
    "approach means runtimes can be added or swapped without "
    "redesigning the orchestration plane.",
    "agentcore source",
    ["architecture"],
)

_add(
    "Why is it important for AgentCore to keep planning logic separate from execution backends?",
    "AgentCore keeps planning logic separate from execution backends so "
    "that task planning, state management, cancellation, memory, and "
    "routing remain independent from individual backends. This allows "
    "runtimes such as Hermes, Kilo, and OpenCode to be added or "
    "replaced without redesigning the orchestration layer. The "
    "RuntimeAdapter interface provides the contract between the two.",
    "agentcore source",
    ["architecture"],
)

_add(
    "What defines the interface between AgentCore's orchestration and its runtime backends?",
    "The boundary between orchestration and runtime backends is the "
    "RuntimeAdapter abstract interface in agentcore/runtimes/base.py. "
    "The orchestration layer calls respond() to send a context to the "
    "runtime and receives a structured RuntimeResponse. It calls "
    "capabilities() to discover what the runtime supports, and "
    "cancel() to interrupt in-flight work. The orchestration layer "
    "never calls runtime-specific APIs directly.",
    "agentcore source",
    ["architecture", "runtime_adapter"],
)

_add(
    "What is the architectural role of the adapter pattern in AgentCore?",
    "A runtime adapter is an implementation of the RuntimeAdapter "
    "abstract interface in agentcore/runtimes/base.py. It bridges the "
    "orchestration layer and a specific execution backend. The adapter "
    "translates AgentCore context into a backend-specific format, "
    "invokes the backend, parses the response, and returns a "
    "structured RuntimeResponse. This is the adapter pattern: a "
    "standardized interface decouples two otherwise incompatible layers.",
    "agentcore source",
    ["architecture", "runtime_adapter"],
)

_add(
    "Through what mechanism does the orchestrator communicate with a runtime adapter?",
    "The adapter interface — the RuntimeAdapter abstract class in "
    "agentcore/runtimes/base.py — is the communication channel. The "
    "orchestrator calls respond(context) to send a context dict and "
    "receives a RuntimeResponse. The adapter also implements "
    "capabilities() to advertise features and cancel() to interrupt. "
    "This interface is the contract between the two layers.",
    "agentcore source",
    ["architecture", "runtime_adapter"],
)

_add(
    "What interface must be implemented to register a custom runtime adapter in AgentCore?",
    "New runtime types are added by implementing the RuntimeAdapter "
    "abstract interface from agentcore/runtimes/base.py. The adapter "
    "must implement respond() and capabilities(). Runtimes are "
    "registered with the RuntimeRegistry, and the built-in Hermes "
    "runtime is auto-registered in agentcore/runtimes/registry.py. "
    "No core code needs to be modified — the orchestrator always "
    "calls the adapter through the abstract interface.",
    "agentcore source",
    ["extensibility", "runtime_adapter"],
)


# ============================================================
# ORCHESTRATION EXAMPLES
# ============================================================

_add(
    "What function does the orchestration layer serve in AgentCore?",
    "The orchestration layer in AgentCore is the decision-making brain. "
    "It handles task planning, state management, scheduling, routing, "
    "and memory coordination. The TaskRegistry tracks task lifecycle, "
    "prevents duplicate execution via locks, and emits lifecycle events. "
    "The OrchestrationEngine coordinates the agent loop.",
    "agentcore source",
    ["orchestration"],
)

_add(
    "How does the orchestrator choose which skills apply to a given task?",
    "The orchestrator uses the SkillRouter in agentcore/router.py to "
    "decide which skills should handle a task. The router matches task "
    "content against skill trigger keywords, producing RoutingResults "
    "with match confidence scores. For runtime selection, the "
    "OrchestrationEngine checks runtime capabilities.",
    "agentcore source",
    ["orchestration"],
)

_add(
    "What task distribution strategies are available in the AgentCore system?",
    "AgentCore's TaskRegistry provides in-process task locking to "
    "prevent duplicate execution. The scheduling flow goes through "
    "TaskState transitions: CREATED to ANALYZING to ROUTING to RUNNING. "
    "The TaskRegistry.acquire_lock() enforces that only one executor "
    "holds a lock. On restart, tasks are recovered from persistence.",
    "agentcore source",
    ["orchestration", "task_lifecycle"],
)

_add(
    "How does AgentCore track task lifecycle state at the orchestration level?",
    "AgentCore manages task state through two layers: the Task dataclass "
    "(agentcore/task.py) which implements a state machine with TaskState "
    "enum and _VALID_TRANSITIONS, and the TaskRegistry "
    "(agentcore/task_registry.py) which tracks TaskRecordStatus. The "
    "Task dataclass enforces valid transitions via _can_transition().",
    "agentcore source",
    ["orchestration", "task_lifecycle"],
)


# ============================================================
# RUNTIME EXAMPLES
# ============================================================

_add(
    "What is the responsibility of a runtime backend within AgentCore's execution model?",
    "A runtime in AgentCore is an execution backend that performs "
    "actual work. Runtimes implement the RuntimeAdapter abstract "
    "interface from agentcore/runtimes/base.py. A runtime responds "
    "to context via respond(), advertises capabilities via "
    "capabilities(), and handles cancellation via cancel().",
    "agentcore source",
    ["runtime"],
)

_add(
    "How does AgentCore pick which runtime to invoke for a task?",
    "AgentCore selects a runtime during the ROUTING phase of the task "
    "state machine. The OrchestratorEngine checks available runtimes "
    "registered with the RuntimeRegistry, querying capabilities() to "
    "find one that supports required features. The built-in "
    "HermesRuntime is auto-registered.",
    "agentcore source",
    ["runtime", "routing"],
)

_add(
    "Can AgentCore run multiple runtimes simultaneously, and how is isolation maintained?",
    "Yes, multiple runtimes can coexist in AgentCore. The RuntimeRegistry "
    "allows registering multiple runtime factories by name. Each runtime "
    "runs as a separate subprocess. The cancel() method terminates the "
    "in-flight subprocess. Runtime failures are isolated.",
    "agentcore source",
    ["runtime", "safety"],
)

_add(
    "How does the actual work get delegated from AgentCore to a runtime?",
    "Execution delegation flows through the RuntimeAdapter interface. "
    "The orchestration layer builds a context dict and calls "
    "RuntimeAdapter.respond(context), receiving a RuntimeResponse with "
    "content, tool_calls, and finish_reason. If finish_reason is "
    "TOOL_CALLS, the agent processes the tool calls via ToolManager "
    "(the runtime must NOT execute tools directly).",
    "agentcore source",
    ["execution", "runtime"],
)


# ============================================================
# RUNTIME ADAPTER EXAMPLES
# ============================================================

_add(
    "Which API methods define the RuntimeAdapter abstract base class contract?",
    "A runtime adapter must implement respond(context) and "
    "capabilities() from the RuntimeAdapter ABC in "
    "agentcore/runtimes/base.py. The cancel() method has a default "
    "no-op. Runtime capabilities must include: text_generation, "
    "tool_calls, external_tool_execution, streaming, and cancellation.",
    "agentcore source",
    ["runtime_adapter"],
)

_add(
    "How does a runtime adapter convert orchestration context into backend-specific calls?",
    "The runtime adapter converts orchestration context by receiving a "
    "context dict and transforming it to a runtime-specific format. For "
    "HermesRuntime, HermesAPI.build_prompt() formats the context into a "
    "text prompt. The adapter invokes the Hermes CLI as a subprocess "
    "and parses output using TOOL_CALL_PATTERN regex.",
    "agentcore source",
    ["runtime_adapter", "execution"],
)

_add(
    "What feature flags should a runtime adapter advertise?",
    "A runtime adapter must advertise capabilities using standardized keys "
    "in RuntimeCapabilities: text_generation, tool_calls, "
    "external_tool_execution, streaming, and cancellation. Each key "
    "should be True only if the runtime supports that feature. "
    "HermesRuntime advertises text_generation=True and cancellation=True.",
    "agentcore source",
    ["runtime_adapter"],
)

_add(
    "How does AgentCore maintain the boundary between orchestration and runtime code?",
    "AgentCore enforces the orchestration/runtime boundary through the "
    "RuntimeAdapter abstract interface. The orchestration layer imports "
    "RuntimeAdapter and related types from base.py, never "
    "runtime-specific modules. The runtime is injected as a dependency. "
    "Runtime selection happens through the RuntimeRegistry.",
    "agentcore source",
    ["runtime_adapter", "orchestration", "extensibility"],
)


# ============================================================
# CANCELLATION EXAMPLES
# ============================================================

_add(
    "How does an active runtime execution get interrupted when a task is cancelled?",
    "Cancellation in AgentCore propagates through the "
    "RuntimeAdapter.cancel() method. When the orchestration layer "
    "cancels a task, it transitions the task to CANCELLED and calls "
    "RuntimeAdapter.cancel() on the active runtime. For HermesRuntime, "
    "cancel() sets _cancelled=True and terminates the subprocess via "
    "process.terminate(), escalating to process.kill() if needed.",
    "agentcore source",
    ["cancellation", "runtime"],
)

_add(
    "What is the runtime adapter's responsibility during a cancellation request?",
    "When cancellation is requested, a runtime adapter must implement "
    "the cancel() method. For HermesRuntime, this sets _cancelled=True "
    "and calls _cancel_in_flight(), which terminates the subprocess "
    "via process.terminate() followed by process.kill() if it doesn't "
    "exit within 5 seconds.",
    "agentcore source",
    ["cancellation", "runtime_adapter"],
)

_add(
    "Trace the sequence of events when a cancellation request flows through AgentCore.",
    "A cancellation request follows this sequence: (1) the task enters "
    "CANCELLED state in the TaskRegistry; (2) the task lock is "
    "force-released via force_release_lock(); (3) "
    "RuntimeAdapter.cancel() is called; (4) HermesRuntime terminates "
    "the subprocess; (5) the runtime returns FinishReason.CANCELLED; "
    "(6) the TASK_CANCELLED event is emitted; (7) the task reaches a "
    "terminal state. Cancellation propagates into the active runtime "
    "execution.",
    "agentcore source",
    ["cancellation", "task_lifecycle"],
)


# ============================================================
# TASK LIFECYCLE EXAMPLES
# ============================================================

_add(
    "What are the possible states a task can be in during its lifecycle?",
    "Tasks in AgentCore transition through states defined in the "
    "TaskState enum: CREATED, ANALYZING, ROUTING, INVESTIGATING, "
    "PLANNING, RUNNING, WAITING_FOR_TOOL, OBSERVING, REPLANNING, "
    "VERIFYING, IMPLEMENTING, COMPLETED, FAILED, CANCELLED, BLOCKED. "
    "The state machine enforces valid transitions via "
    "_VALID_TRANSITIONS. Terminal states are COMPLETED, FAILED, "
    "CANCELLED, and BLOCKED.",
    "agentcore source",
    ["task_lifecycle"],
)

_add(
    "How does a newly created task begin executing in AgentCore?",
    "A newly created task transitions from CREATED to RUNNING through "
    "the OrchestratorEngine's state machine. The engine moves the "
    "task through: CREATED to ANALYZING to ROUTING to INVESTIGATING "
    "to PLANNING to RUNNING (delegates via RuntimeAdapter.respond()). "
    "Each transition is recorded via Task.setState().",
    "agentcore source",
    ["task_lifecycle"],
)

_add(
    "What events cause a task to move from one state to another?",
    "Task state changes are triggered by the OrchestratorEngine's "
    "event-driven loop. Each transition corresponds to a completed "
    "phase: context analysis, skill routing, plan generation, "
    "execution start. Transitions also happen in response to runtime "
    "outcomes. The TaskRegistry emits TASK_STATE_CHANGED events.",
    "agentcore source",
    ["task_lifecycle", "events"],
)

_add(
    "How does an agent track progress when executing across multiple runtimes?",
    "AgentCore tracks task progress across multiple runtimes through "
    "the TaskState machine and TaskRecord. When a runtime returns "
    "tool_calls, the agent executes them via ToolManager and observes "
    "results. If a runtime fails, the agent can select a different "
    "runtime, since the TaskContextData preserves the plan and "
    "observations.",
    "agentcore source",
    ["task_lifecycle", "runtime"],
)

_add(
    "What data is recorded when a task transitions to the cancelled state?",
    "When a task enters the CANCELLED state, the TaskRegistry emits a "
    "TASK_CANCELLED event with the task_id, the cancellation reason "
    "(in metadata), and the current state. The lock is "
    "force-released. The state is terminal — no further transitions "
    "are allowed afterward.",
    "agentcore source",
    ["task_lifecycle", "cancellation"],
)


# ============================================================
# FAILURE HANDLING EXAMPLES
# ============================================================

_add(
    "What happens if a runtime process crashes or freezes during execution?",
    "When a runtime crashes or becomes unresponsive, the "
    "RuntimeAdapter.respond() method returns a RuntimeResponse with "
    "FinishReason.ERROR or FinishReason.TIMEOUT. For HermesRuntime, "
    "TimeoutExpired is caught, _cancel_in_flight() terminates the "
    "process, and a response with TIMEOUT is returned. The "
    "OrchestrationEngine can retry or transition to FAILED.",
    "agentcore source",
    ["failure_handling", "runtime"],
)

_add(
    "How does AgentCore respond when a task execution attempt fails?",
    "When a task execution fails, the OrchestrationEngine detects the "
    "FinishReason.ERROR or TIMEOUT from the RuntimeResponse. It logs "
    "the failure, checks if a retry is possible within max_replans, "
    "and may transition to REPLANNING. If retries are exhausted, "
    "the task transitions to FAILED. The failure is stored as an "
    "OUTCOME-type memory.",
    "agentcore source",
    ["failure_handling", "task_lifecycle"],
)

_add(
    "What error handling occurs when a runtime adapter encounters a failure?",
    "When a runtime adapter fails, HermesRuntime catches exceptions in "
    "respond(): TimeoutExpired returns FinishReason.TIMEOUT, "
    "FileNotFoundError returns ERROR, and generic exceptions return "
    "ERROR with the exception string. The OrchestrationEngine checks "
    "finish_reason and either retries or transitions to FAILED. The "
    "ObservationCollector captures runtime.error events. No exception "
    "propagates to crash the orchestrator.",
    "agentcore source",
    ["failure_handling", "runtime_adapter"],
)

_add(
    "What retry mechanisms does AgentCore use when a task fails transiently?",
    "AgentCore supports retry through the OrchestratorEngine's replanning "
    "mechanism. When a runtime returns FinishReason.ERROR or TIMEOUT, "
    "the engine checks max_replans (default 3). If retries remain, the "
    "task transitions to REPLANNING. The failure observation is "
    "included in the context for replanning.",
    "agentcore source",
    ["failure_handling", "task_lifecycle"],
)


# ============================================================
# ROUTING EXAMPLES
# ============================================================

_add(
    "How does AgentCore match a task to the appropriate runtime for execution?",
    "During the ROUTING phase, the OrchestrationEngine checks "
    "available runtimes in the RuntimeRegistry, querying "
    "capabilities(). The SkillRouter matches task content against "
    "skill trigger keywords. If no runtime supports required "
    "capabilities, the task enters BLOCKED state.",
    "agentcore source",
    ["routing"],
)

_add(
    "What factors determine which runtime gets selected for a task?",
    "The routing layer matches tasks to runtimes based on capabilities "
    "requirements. The OrchestratorEngine checks "
    "RuntimeAdapter.capabilities() against the task's needs: "
    "text_generation, tool_calls, streaming, cancellation, "
    "external_tool_execution. The SkillRouter matches task content "
    "against skill keywords.",
    "agentcore source",
    ["routing", "runtime_adapter"],
)

_add(
    "Can the runtime and skill selection logic be customized for different use cases?",
    "Yes, AgentCore's routing can be customized through the SkillRouter. "
    "Custom skills define trigger_keywords in SKILL.md frontmatter. "
    "The router also has _FALLBACK_KEYWORDS for built-in categories. "
    "For runtime customization, the RuntimeRegistry allows registering "
    "custom runtime factories by name. The SkillRouter can be "
    "subclassed or replaced.",
    "agentcore source",
    ["routing", "extensibility"],
)


# ============================================================
# EXECUTION EXAMPLES
# ============================================================

_add(
    "What is the step-by-step process when an agent works through a task?",
    "When an agent works through a task, the orchestration layer calls "
    "RuntimeAdapter.respond(context) with a context dict. The runtime "
    "adapter formats this into a prompt, invokes the backend, parses "
    "the output, and returns a RuntimeResponse with content, "
    "tool_calls, and finish_reason. If finish_reason is TOOL_CALLS, "
    "the agent processes tool calls via ToolManager (the runtime must "
    "NOT execute tools directly).",
    "agentcore source",
    ["execution", "runtime"],
)

_add(
    "How does AgentCore switch between runtimes during task execution?",
    "AgentCore delegates execution to different runtimes through the "
    "RuntimeAdapter interface. The orchestration layer calls "
    "respond(context) on the active runtime adapter. To use a "
    "different runtime, the OrchestratorEngine selects a new "
    "RuntimeAdapter from the RuntimeRegistry during the ROUTING "
    "phase. Each adapter implements the same interface.",
    "agentcore source",
    ["execution", "runtime_adapter"],
)

_add(
    "What is a RuntimeResponse and how is it structured?",
    "A RuntimeResponse in agentcore/runtimes/base.py is the structured "
    "output from any RuntimeAdapter. It contains: content (str, the "
    "model's text output), tool_calls (List[ToolCall], parsed tool "
    "invocations), finish_reason (FinishReason enum: STOP, TOOL_CALLS, "
    "TIMEOUT, ERROR, CANCELLED), and metadata (dict). The "
    "has_tool_calls property checks if tool_calls is non-empty.",
    "agentcore source",
    ["execution", "runtime_adapter"],
)

_add(
    "What does the COMPLETE marker signify in AgentCore's runtime protocol?",
    "The COMPLETE marker in agentcore/runtimes/hermes.py is a text "
    "signal that the Hermes CLI outputs when the model is done "
    "generating a response. The HermesRuntime checks for this marker "
    "during _parse_response(). When found, finish_reason is set to "
    "FinishReason.STOP. The COMPLETE marker provides explicit "
    "signaling of completion, distinguishing intentional completion "
    "from truncation.",
    "agentcore source",
    ["execution", "runtime"],
)

_add(
    "When does the OBSERVING state occur in AgentCore's execution loop?",
    "The OBSERVING state occurs after tool calls are executed. When "
    "a RuntimeResponse returns FinishReason.TOOL_CALLS, the orchestrator "
    "enters WAITING_FOR_TOOL, executes tool calls via ToolManager, "
    "then transitions to OBSERVING. During OBSERVING, tool results are "
    "processed: stored in the task context, observations created, and "
    "results fed back into the next respond() call.",
    "agentcore source",
    ["execution", "task_lifecycle", "events"],
)

_add(
    "What is FinishReason in AgentCore and what values can it take?",
    "FinishReason is an enum in agentcore/runtimes/base.py that "
    "indicates why a RuntimeResponse ended. Values: STOP (model "
    "produced final text), TOOL_CALLS (model requested tool calls), "
    "TIMEOUT (runtime timed out), ERROR (runtime error), CANCELLED "
    "(request was cancelled). The HermesRuntime sets these based on "
    "parsing: COMPLETE marker in output maps to STOP, "
    "TOOL_CALL_PATTERN matches map to TOOL_CALLS, TimeoutExpired "
    "maps to TIMEOUT, and the _cancelled flag maps to CANCELLED.",
    "agentcore source",
    ["execution", "runtime"],
)

_add(
    "How does AgentCore handle tool calls that come from a runtime?",
    "When a RuntimeResponse contains tool_calls, the OrchestrationEngine "
    "extracts them and passes them to the ToolManager for execution. "
    "The ToolManager runs each tool in the proper environment (e.g. "
    "subprocess for shell commands) and collects ToolResults. These "
    "results are observed via the ObservationCollector creating "
    "TOOL_CALL_COMPLETED observations, stored in the task context, "
    "and fed back to the runtime in the next respond() call. This "
    "separation ensures that tool execution is controlled by the "
    "orchestration layer, not delegated to the runtime.",
    "agentcore source",
    ["execution", "runtime_adapter", "safety"],
)


# ============================================================
# EXTENSIBILITY EXAMPLES
# ============================================================

_add(
    "How can new execution backends be plugged into AgentCore without code changes?",
    "AgentCore is extensible through several extension points that "
    "require no core code modification: (1) RuntimeAdapter interface "
    "for new runtimes; (2) MemoryBackend interface for custom memory "
    "backends; (3) ObservationStore interface for custom observation "
    "storage; (4) Skill system loaded from .skill.md files; "
    "(5) EventBus observer subscriptions. All extensions use "
    "dependency injection and abstract interfaces.",
    "agentcore source",
    ["extensibility"],
)

_add(
    "How does the RuntimeAdapter interface enable plugging in custom runtimes?",
    "The RuntimeAdapter interface in agentcore/runtimes/base.py enables "
    "extensibility by providing a stable contract between orchestration "
    "and execution backends. Third parties implement respond() and "
    "capabilities() without modifying core code. The RuntimeRegistry."
    "register() method allows registering custom adapters by name. "
    "The orchestrator always calls the adapter through the abstract "
    "interface.",
    "agentcore source",
    ["extensibility", "runtime_adapter"],
)

_add(
    "How does AgentCore's ObservationStore interface support custom storage backends?",
    "AgentCore's ObservationStore interface in agentcore/observations.py "
    "defines add(), get(), list_by_task(), list_by_session(), and "
    "clear(). Third parties implement these to create custom observation "
    "storage. The ObservationCollector consumes observations through "
    "the abstract interface. Custom stores can be injected via the "
    "constructor.",
    "agentcore source",
    ["extensibility", "events"],
)

_add(
    "How can third parties provide custom memory backends?",
    "AgentCore's MemoryBackend ABC defines abstract methods search(), "
    "store(), update(), list() plus optional methods with safe defaults. "
    "The MemoryManager calls backend methods through try/except and uses "
    "hasattr() for optional methods. No core module imports a specific "
    "backend. A third party can implement MemoryBackend for any storage "
    "system and inject it into MemoryManager.",
    "agentcore source",
    ["extensibility", "memory"],
)


# ============================================================
# SAFETY EXAMPLES
# ============================================================

_add(
    "How does AgentCore prevent a runtime crash from affecting the orchestrator?",
    "AgentCore enforces security boundaries through process isolation. "
    "Each runtime adapter runs as a separate subprocess. The "
    "orchestration layer communicates only via the RuntimeAdapter "
    "interface. If a runtime crashes or is compromised, the process "
    "boundary contains the failure.",
    "agentcore source",
    ["safety", "runtime_adapter"],
)

_add(
    "How does AgentCore limit resource consumption during task execution?",
    "AgentCore enforces resource limits through AgentConfig: "
    "max_iterations (default 10), max_tool_calls (default 50), "
    "max_runtime_seconds (default 300), and timeout (300). The "
    "OrchestrationEngine checks these limits. The HermesRuntime "
    "enforces timeout via subprocess.communicate(timeout=self.timeout). "
    "The TaskRegistry uses locks to prevent resource contention.",
    "agentcore source",
    ["safety", "runtime"],
)

_add(
    "How does AgentCore prevent a compromised runtime from affecting the orchestrator?",
    "AgentCore prevents a compromised runtime through process isolation "
    "and interface constraints. Each runtime runs as a separate "
    "subprocess. The orchestration layer communicates only through the "
    "RuntimeAdapter interface. The runtime cannot access "
    "TaskRegistry, MemoryBackend, or Task data. If the runtime crashes, "
    "the process boundary contains it.",
    "agentcore source",
    ["safety", "runtime_adapter"],
)

_add(
    "How does AgentCore handle resource exhaustion during task execution?",
    "AgentCore handles resource exhaustion through the runtime adapter's "
    "timeout mechanism. The HermesRuntime enforces a configurable "
    "timeout via subprocess.communicate(timeout=self.timeout). If "
    "exceeded, TimeoutExpired is caught, _cancel_in_flight() "
    "terminates the process, and FinishReason.TIMEOUT is returned. "
    "The OrchestrationEngine can then retry or fail the task.",
    "agentcore source",
    ["safety", "runtime"],
)

_add(
    "What is the resource guard pattern used in AgentCore?",
    "AgentCore uses a resource guard pattern through AgentConfig "
    "limits: max_iterations, max_tool_calls, max_runtime_seconds, "
    "and timeout. The OrchestrationEngine checks these during the "
    "agent loop. The HermesRuntime enforces process timeouts. The "
    "TaskRegistry uses locks to prevent concurrent execution of "
    "the same task. Together these form defense-in-depth.",
    "agentcore source",
    ["safety", "runtime_adapter"],
)


# ============================================================
# EVENTS EXAMPLES
# ============================================================

_add(
    "How does AgentCore react to events produced by runtimes?",
    "AgentCore handles asynchronous events from runtimes through the "
    "ObservationCollector and EventBus. The collector subscribes to "
    "EventBus events and translates them into structured Observation "
    "objects with stable correlation IDs. When runtimes produce events, "
    "the HermesEventBridge maps Hermes lifecycle callbacks to "
    "Argus EventType values. The MemoryHarvester then extracts memory "
    "candidates.",
    "agentcore source",
    ["events", "runtime_adapter"],
)

_add(
    "Describe the event-driven model AgentCore uses for state transitions.",
    "AgentCore uses an event-driven model where state changes emit typed "
    "events through the EventBus. The EventBus is created by the "
    "agent and passed to the TaskRegistry, ObservationCollector, and "
    "MemoryManager. State changes emit AgentEvent objects with "
    "structured data, task_id, iteration, and metadata. The EventBus "
    "is synchronous. If no EventBus is provided, events are dropped.",
    "agentcore source",
    ["events", "orchestration"],
)

_add(
    "What event types does AgentCore define for task lifecycle tracking?",
    "AgentCore's EventType enum defines events for every phase: "
    "TASK_STARTED, TASK_STATE_CHANGED, TASK_COMPLETED, TASK_FAILED, "
    "TASK_CANCELLED, ITERATION_STARTED, ROUTE_SELECTED, "
    "MODEL_REQUEST_STARTED, MODEL_RESPONSE_RECEIVED, "
    "TOOL_CALL_STARTED, TOOL_CALL_COMPLETED, RUNTIME_ERROR, "
    "OBSERVATION_CREATED, MEMORY_STORE_STARTED, MEMORY_RECALL_STARTED, "
    "MEMORY_ERROR. These are emitted by the EventBus, consumed by "
    "observers, and translated to Observations by the "
    "ObservationCollector.",
    "agentcore source",
    ["events"],
)

_add(
    "How does the ObservationCollector correlate events to tasks and sessions?",
    "The ObservationCollector in agentcore/observations.py correlates "
    "events to tasks and sessions by extracting identifiers from event "
    "metadata and data. It resolves session_id and task_id from "
    "metadata, turn_id from metadata or data, and tool_call_id from "
    "metadata. For MODEL_REQUEST_STARTED events, a model_request_id "
    "is generated and tracked. Each observation gets a sequence "
    "number for ordering.",
    "agentcore source",
    ["events"],
)

_add(
    "What is the difference between EventBus events and Observations?",
    "In AgentCore, EventBus events are transient signals — they fire "
    "synchronously and are only consumed by subscribed observers. If no "
    "observers are subscribed, events are dropped. Observations are "
    "durable, queryable records stored in an ObservationStore. The "
    "ObservationCollector bridges them by translating EventBus events "
    "into Observations with stable correlation IDs. Observations feed "
    "the MemoryHarvester; events feed observers.",
    "agentcore source",
    ["events", "memory"],
)

_add(
    "How does AgentCore handle observation deduplication?",
    "Observation deduplication happens in the "
    "DBObsidianObservationStore via DB-Obsidian's built-in dedupe. "
    "The add() method passes dedupe=True to MemoryStore.add(), which "
    "checks for existing observations with the same content_hash, "
    "project, and type. The store maintains an in-memory index of "
    "observation.id to memory.id. The MemoryHarvester also "
    "deduplicates by tracking seen_ids within a batch.",
    "agentcore source",
    ["events", "persistence"],
)

_add(
    "How does AgentCore's EventBus handle a failing subscriber?",
    "AgentCore's EventBus handles subscriber failures by catching "
    "exceptions in the emit() method's subscriber iteration loop. "
    "Each subscriber callback is wrapped in try/except. If a subscriber "
    "raises, it is caught and logged, and the EventBus continues "
    "processing remaining subscribers. The emit() method returns "
    "None — no indication of subscriber failures.",
    "agentcore source",
    ["events"],
)


# ============================================================
# PERSISTENCE EXAMPLES
# ============================================================

_add(
    "How does AgentCore restore tasks after a process restart?",
    "AgentCore persists task state through the TaskPersistenceManager "
    "using a PersistenceBackend. On startup, "
    "recover_from_persistence() calls "
    "persistence.recover_incomplete_tasks() to find tasks in "
    "non-terminal states. These are registered with status "
    "RECOVERED. The persistence layer uses atomic writes and schema "
    "versioning.",
    "agentcore source",
    ["persistence", "task_lifecycle"],
)

_add(
    "Which parts of AgentCore's runtime state survive a restart?",
    "AgentCore persists task state via TaskPersistenceManager to the "
    "filesystem. TaskRegistry records are in-memory only — recreated "
    "on startup from persisted tasks. Observations are persisted via "
    "DBObsidianObservationStore when configured. Memory is persisted "
    "via DBObsidianBackend (SQLite). The EventBus itself is ephemeral. "
    "The key distinction: task state and memory can be durable; "
    "registry, event bus, and runtime context are ephemeral.",
    "agentcore source",
    ["persistence", "memory"],
)

_add(
    "How does AgentCore's TaskPersistenceManager handle security filtering?",
    "The TaskPersistenceManager applies security filtering before "
    "persisting task state. The _sanitize_metadata() function strips "
    "fields from task metadata. The _filter_content() function scans "
    "serialized task data for patterns matching API keys, passwords, "
    "secrets, and tokens. This filtering happens before the atomic write.",
    "agentcore source",
    ["persistence", "safety"],
)

_add(
    "How does AgentCore ensure atomic writes during persistence?",
    "AgentCore ensures atomic writes in the FilesystemPersistenceBackend "
    "by writing to a temporary file first, then atomically renaming it. "
    "The write flow: (1) serialize data to JSON; (2) write to a temp "
    "file; (3) flush and fsync; (4) os.replace(temp_path, target_path) "
    "which is atomic. This prevents partial writes on crash.",
    "agentcore source",
    ["persistence", "safety"],
)


# ============================================================
# SHUTDOWN EXAMPLES
# ============================================================

_add(
    "What occurs during graceful shutdown of an AgentCore instance?",
    "Graceful shutdown cleans up in-flight tasks before exiting. "
    "TaskRegistry.force_release_lock() releases all task locks. "
    "Active runtime adapters receive cancel() calls. Tasks in "
    "non-terminal states are persisted as CANCELLED. The "
    "PersistenceManager flushes state. MemoryManager.close() closes "
    "database connections.",
    "agentcore source",
    ["shutdown", "cancellation"],
)

_add(
    "How does AgentCore prevent resource leaks during shutdown?",
    "AgentCore ensures no resource leaks during shutdown through multiple "
    "mechanisms. HermesRuntime._cancel_in_flight() terminates the "
    "subprocess via process.terminate() with a 5-second timeout, "
    "escalating to process.kill(). TaskRegistry.force_release_lock() "
    "releases all locks. MemoryManager.close() closes the SQLite "
    "connection. All cleanup is in finally blocks or try/except.",
    "agentcore source",
    ["shutdown", "cancellation", "failure_handling"],
)

_add(
    "What is the order of cleanup operations during AgentCore shutdown?",
    "The AgentCore shutdown sequence is ordered: (1) runtime "
    "subprocesses are terminated via RuntimeAdapter.cancel(); (2) "
    "memory backend connections are closed; (3) observation store "
    "connections are closed; (4) pending task states are flushed to "
    "storage; (5) TaskRegistry clears all locks and records. Each "
    "step is wrapped in try/except.",
    "agentcore source",
    ["shutdown", "safety"],
)


# ============================================================
# CONTRASTIVE CORRECTION EXAMPLES
# (Step 7: wrong answer → correct answer)
# ============================================================

CORRECTION_CANDIDATES.extend(
    [
        CorrectionPair(
            instruction=(
                "Through what interface does the orchestration layer "
                "communicate with execution backends?"
            ),
            wrong_output=(
                "The adapter interface is just a thin pass-through that "
                "forwards the orchestrator's commands directly to the "
                "runtime with no transformation needed."
            ),
            correct_output=(
                "The adapter interface (RuntimeAdapter in agentcore/runtimes/"
                "base.py) is a translation layer. It converts the "
                "orchestration context dict into a runtime-specific format "
                "(HermesRuntime builds a text prompt via "
                "HermesAPI.build_prompt), invokes the backend, parses the "
                "response, and returns a structured RuntimeResponse with "
                "content, tool_calls, and finish_reason."
            ),
            rationale=(
                "The adapter does real work — it transforms the context "
                "dict into a runtime-specific prompt, invokes a "
                "subprocess, and parses TOOL_CALL directives."
            ),
            domains=["runtime_adapter", "execution", "runtime"],
        ),
        CorrectionPair(
            instruction="How can new execution backends be integrated into AgentCore?",
            wrong_output=(
                "AgentCore allows new runtimes to be added by editing the "
                "orchestrator's runtime selection code and adding a new "
                "conditional branch for each runtime type."
            ),
            correct_output=(
                "New execution backends are added by implementing the "
                "RuntimeAdapter abstract interface. The adapter implements "
                "respond() and capabilities(). Runtimes are registered with "
                "the RuntimeRegistry, and the built-in Hermes runtime is "
                "auto-registered. No core AgentCore code needs modification."
            ),
            rationale=(
                "AgentCore uses dependency inversion: extensions implement "
                "abstract interfaces and register via a registry."
            ),
            domains=["extensibility", "runtime_adapter"],
        ),
        CorrectionPair(
            instruction="What should happen when an active runtime operation is cancelled?",
            wrong_output=(
                "When a task is cancelled, AgentCore should just set a "
                "cancelled flag on the task record and let the running "
                "operation finish naturally."
            ),
            correct_output=(
                "When a task is cancelled, AgentCore must propagate "
                "cancellation into the active runtime execution. The "
                "OrchestrationEngine calls RuntimeAdapter.cancel() on the "
                "active runtime. For HermesRuntime, this sets "
                "_cancelled=True and terminates the subprocess via "
                "process.terminate(), escalating to process.kill() if "
                "needed."
            ),
            rationale=(
                "Cancellation must propagate into the active runtime "
                "execution to actually interrupt in-flight work."
            ),
            domains=["cancellation", "runtime", "orchestration"],
        ),
        CorrectionPair(
            instruction="How should AgentCore respond when a runtime encounters an error?",
            wrong_output=(
                "When a runtime fails, AgentCore should catch the exception, "
                "log it, and immediately mark the task as failed. The "
                "error should be re-raised."
            ),
            correct_output=(
                "When a runtime fails, AgentCore catches the exception "
                "inside the adapter's respond() and returns a "
                "RuntimeResponse with FinishReason.ERROR or TIMEOUT. "
                "For HermesRuntime, TimeoutExpired returns TIMEOUT, "
                "FileNotFoundError returns ERROR, and generic exceptions "
                "return ERROR. The engine checks max_replans and either "
                "retries or transitions to FAILED."
            ),
            rationale=(
                "Runtime failures are caught at the adapter boundary and "
                "returned as structured RuntimeResponse objects."
            ),
            domains=["failure_handling", "runtime"],
        ),
        CorrectionPair(
            instruction="Distinguish between the memory store and the task state tracker.",
            wrong_output=(
                "Agent memory and task state are the same thing. Memory is "
                "just the current task state stored in memory for the agent."
            ),
            correct_output=(
                "Agent memory and task state are separate concerns. Task "
                "state is managed by the Task dataclass and TaskRegistry — "
                "it tracks the current phase of a task via TaskState enum "
                "and persists to the filesystem. Memory is managed by "
                "MemoryManager and MemoryBackend — it stores reusable "
                "knowledge. Task state is single-task lifecycle; memory is "
                "cross-task searchable."
            ),
            rationale=(
                "Memory is cross-task, searchable knowledge; task state "
                "is single-task lifecycle tracking."
            ),
            domains=["memory", "task_lifecycle", "orchestration"],
        ),
        CorrectionPair(
            instruction="How does AgentCore transfer state to a runtime for execution?",
            wrong_output=(
                "The orchestrator shares state with runtimes by giving the "
                "runtime a direct reference to the MemoryBackend and "
                "TaskRegistry. The runtime can read and write memory."
            ),
            correct_output=(
                "AgentCore shares state through a context dict passed to "
                "RuntimeAdapter.respond(). The ContextBuilder assembles this "
                "from ProjectContextData, TaskContextData, and "
                "RuntimeContextData. Retrieved memories are embedded as "
                "MemoryContextData. Runtimes NEVER access MemoryBackend, "
                "TaskRegistry, or ObservationStore directly."
            ),
            rationale=(
                "Runtimes receive only a formatted context dict. They "
                "cannot directly access MemoryBackend or TaskRegistry."
            ),
            domains=["runtime_adapter", "memory", "orchestration"],
        ),
        CorrectionPair(
            instruction=(
                "How does AgentCore ensure process-level isolation "
                "between the orchestrator and runtime processes?"
            ),
            wrong_output=(
                "AgentCore provides isolation by running all runtimes "
                "in the same process as the orchestrator. Memory is "
                "shared and isolated by Python's GIL."
            ),
            correct_output=(
                "AgentCore provides isolation by running each runtime as a "
                "separate subprocess with its own process memory space. "
                "HermesRuntime spawns the Hermes CLI via "
                "subprocess.Popen. The orchestration layer communicates "
                "only through the RuntimeAdapter interface. If a runtime "
                "crashes, the process boundary contains the failure."
            ),
            rationale=(
                "Runtimes run as separate subprocesses with process-level "
                "isolation, not in-process."
            ),
            domains=["safety", "runtime", "runtime_adapter"],
        ),
        CorrectionPair(
            instruction="How should the agent respond when a runtime returns an error?",
            wrong_output=(
                "AgentCore immediately marks the task as failed and moves on. "
                "No retry or recovery is attempted."
            ),
            correct_output=(
                "AgentCore catches the error inside the adapter's "
                "respond() and returns FinishReason.ERROR or TIMEOUT. "
                "The OrchestrationEngine checks max_replans (default 3). "
                "If retries remain, the task transitions to REPLANNING "
                "— the engine can adjust the plan or switch runtimes. "
                "After max_replans is exhausted, the task moves to FAILED."
            ),
            rationale=(
                "AgentCore does intelligent replanning on runtime failure, not immediate failure."
            ),
            domains=["failure_handling", "runtime", "task_lifecycle"],
        ),
    ]
)


# ============================================================
# ADDITIONAL MEMORY — deeper regression fix coverage
# ============================================================

_add(
    "Why is memory considered optional rather than mandatory in AgentCore?",
    "Memory is optional in AgentCore because the system must function even "
    "when no memory backend is available. The MemoryManager constructor "
    "sets self._enabled = backend is not None. When enabled is False, "
    "search() returns [], store() returns None, get() returns None, and "
    "all operations short-circuit. This ensures AgentCore can operate in "
    "a stateless mode for testing or ephemeral tasks. The MemoryManager "
    "never raises when memory is unavailable — it silently degrades. "
    "This is an architectural safety guarantee.",
    "agentcore source",
    ["memory", "safety"],
)

_add(
    "How does the MemoryManager handle the delete operation on memory records?",
    "The MemoryManager.delete() method deletes a single memory by ID. "
    "It checks if memory is enabled, then checks if the backend supports "
    "delete via hasattr. If supported, it calls backend.delete(memory_id) "
    "and returns the boolean result. If the backend doesn't support "
    "delete or the call fails, it returns False. The method is wrapped "
    "in try/except and logs a warning on failure. The InMemoryBackend "
    "deletes from its _records dict; the DBObsidianBackend delegates "
    "to the MemoryStore.",
    "agentcore source",
    ["memory", "failure_handling"],
)

_add(
    "How does the MemoryHarvester extract text from observation payloads?",
    "The MemoryHarvester uses _extract_text_from_payload() in "
    "agentcore/harvesting.py to pull meaningful text from observation "
    "payloads. It tries multiple extraction strategies: extract 'text' "
    "field, then 'error', then 'result', then joins 'stdout' and "
    "'stderr'. The extracted text is filtered through "
    "_is_low_information() which checks for empty strings, whitespace, "
    "and boilerplate like 'OK', 'null', and '200 OK'. Only meaningful "
    "text becomes a memory candidate.",
    "agentcore source",
    ["memory", "events"],
)

_add(
    "How does the MemoryHarvester generate deterministic candidate IDs?",
    "The _generate_candidate_id() function creates a deterministic ID "
    "from task_id, memory_type, and normalized content. Normalization: "
    "lowercase, collapse whitespace, strip, remove punctuation. If "
    "task_id is empty, uses session_id or 'global'. The result is a "
    "SHA-256 hash truncated to 16 hex characters. This ensures the "
    "same observation always produces the same candidate ID, enabling "
    "idempotency and deduplication.",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "How does the MemoryHarvester filter out low-information candidates?",
    "The MemoryHarvester uses _is_low_information() in harvesting.py to "
    "filter candidates that add no value. Checks: empty or whitespace-only "
    "text, text that is only a number/UUID/boolean, status strings "
    "like 'OK', 'null', '200', 'true', 'false', text shorter than 5 "
    "characters, and text that is only punctuation. This prevents the "
    "memory database from filling with useless entries.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does the MemoryHarvester handle persistence failures?",
    "The _persist_candidates() method wraps all persistence in "
    "try/except. If backend.store() fails, the exception is caught, "
    "logged at debug level, and the candidate is skipped. If "
    "update_confidence() fails, the same happens. The harvester does "
    "NOT raise on persistence failures — it logs and continues. If no "
    "backend is configured, candidates are produced but not persisted.",
    "agentcore source",
    ["memory", "failure_handling"],
)

_add(
    "How does the MemoryHarvester map observation types to memory types?",
    "The _EXTRACTION_RULES dict in harvesting.py maps observation types: "
    "'task.completed' creates a TASK memory (importance 0.7), "
    "'task.failed' creates an OUTCOME memory (importance 0.3), "
    "'task.cancelled' creates an OUTCOME memory (importance 0.3), "
    "'tool_call.completed' creates a FACT memory (importance 0.5), "
    "'runtime.error' creates an ERROR memory (importance 0.3). Each "
    "extractor handles its payload format and returns a "
    "MemoryCandidate or None if content is too low-information.",
    "agentcore source",
    ["memory", "events"],
)

_add(
    "How does AgentCore's memory handle the INFERRED confidence level?",
    "The INFERRED confidence level (0.5) is assigned when a memory "
    "candidate is derived from multiple observations (related_"
    "observation_count > 1) but lacks direct verification. In the "
    "MemoryConfidenceClassifier, this happens when the observation type "
    "is 'task.completed' but the text lacks verification signals. "
    "The _confidence_to_float() function maps INFERRED to 0.5. "
    "Future observations with verification can upgrade INFERRED "
    "memories to VERIFIED.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore's memory handle the UNKNOWN confidence level?",
    "The UNKNOWN confidence level (0.3) is the fallback when no "
    "evidence supports a higher confidence. In the "
    "MemoryConfidenceClassifier, this is assigned when the observation "
    "type is unrecognized or the payload text is empty or low-"
    "information. The _confidence_to_float() function maps UNKNOWN "
    "to 0.3. These memories rank lowest. Future observations with "
    "verification can upgrade them.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore handle concurrent memory access from multiple threads?",
    "AgentCore handles concurrent memory access through backend-level "
    "synchronization. The InMemoryBackend relies on CPython's GIL for "
    "dict operation atomicity. The DBObsidianBackend uses a threading.Lock "
    "for all operations, serializing access. SQLite's WAL mode allows "
    "concurrent reads. The MemoryManager does not add its own locking — "
    "it delegates to the backend. The MemoryHarvester uses a threading."
    "Lock for its _lock attribute.",
    "agentcore source",
    ["memory", "safety"],
)

_add(
    "How does the MemoryManager.close() method work?",
    "The MemoryManager.close() method closes the backend if it supports "
    "closing. It checks if self._backend exists and has a close() method. "
    "The DBObsidianBackend.close() calls self.db.close(). "
    "The InMemoryBackend.close() is a no-op. This is called during "
    "graceful shutdown. It's wrapped in try/except so database close "
    "failures don't crash shutdown.",
    "agentcore source",
    ["memory", "shutdown"],
)

_add(
    "How does AgentCore integrate memory with the agent loop planning phase?",
    "During the PLANNING phase, the OrchestrationEngine retrieves "
    "relevant memories via MemoryManager.retrieve_relevant_memory(). "
    "These memories provide historical context about similar tasks, "
    "known issues, and successful approaches. The retrieved memories "
    "are included in TaskContextData and passed to the runtime "
    "context. The agent uses this context to avoid repeating mistakes "
    "and leverage past solutions.",
    "agentcore source",
    ["memory", "orchestration"],
)


# ============================================================
# ADDITIONAL SAFETY
# ============================================================

_add(
    "What is the process isolation model used by AgentCore runtimes?",
    "AgentCore's process isolation model runs each runtime as a "
    "separate subprocess, communicating through the RuntimeAdapter "
    "interface. The HermesRuntime spawns the Hermes CLI via "
    "subprocess.Popen with stdin/stdout pipes. The runtime runs in "
    "its own process memory space — shared memory and direct "
    "function calls are impossible across the boundary. This means "
    "a runtime crash, memory leak, or compromise cannot affect the "
    "orchestrator process.",
    "agentcore source",
    ["safety", "runtime"],
)


# ============================================================
# ADDITIONAL ROUTING
# ============================================================

_add(
    "How does the SkillRouter prioritize routing when multiple skills trigger?",
    "The SkillRouter in agentcore/router.py computes a match confidence "
    "for each skill based on trigger keyword overlap. When multiple "
    "skills trigger, the router sorts matches by confidence descending, "
    "then by weight. Skills with higher confidence are selected first. "
    "The router also consults _FALLBACK_KEYWORDS for skills without "
    "triggers. The top N matches are returned as selected_skills.",
    "agentcore source",
    ["routing"],
)

_add(
    "What happens when no skills match a task in AgentCore's routing?",
    "When no skills match, the SkillRouter returns an empty "
    "selected_skills list. The OrchestrationEngine proceeds in default "
    "mode with the primary runtime. The ROUTE_SELECTED event is emitted "
    "with an empty skills list. This is not an error — the task is "
    "handled by the base agent without specialized skill guidance.",
    "agentcore source",
    ["routing"],
)


# ============================================================
# ADDITIONAL CANCELLATION
# ============================================================

_add(
    "How does AgentCore handle cancellation before a task starts running?",
    "When a task is cancelled before entering RUNNING state, the "
    "TaskRegistry transitions it directly to CANCELLED. Since no runtime "
    "is active, cancel() on the adapter is not called — no subprocess to "
    "terminate. The task lock is released via release_lock() or "
    "force_release_lock(). The TASK_CANCELLED event is emitted. The "
    "state is persisted as CANCELLED for later recovery recognition.",
    "agentcore source",
    ["cancellation", "task_lifecycle"],
)


# ============================================================
# ADDITIONAL TASK LIFECYCLE
# ============================================================

_add(
    "What is the difference between BLOCKED and FAILED states in AgentCore?",
    "In AgentCore's TaskState machine, BLOCKED and FAILED are different. "
    "FAILED indicates the task encountered an unrecoverable error. "
    "BLOCKED indicates the task cannot proceed due to an external "
    "constraint (e.g. no suitable runtime available). BLOCKED is "
    "recoverable — when the constraint is resolved, the task can be "
    "resumed. FAILED is not recoverable. The TaskRegistry."
    "list_resumable() excludes blocked tasks.",
    "agentcore source",
    ["task_lifecycle"],
)

_add(
    "How does AgentCore validate that a state transition is allowed?",
    "AgentCore validates state transitions in the Task dataclass via "
    "_can_transition() and _VALID_TRANSITIONS in agentcore/task.py. "
    "Each TaskState maps to a set of allowed next states. The "
    "Task.setState() method calls _can_transition() before changing "
    "state. If the transition is invalid, "
    "InvalidStateTransitionError is raised. This ensures the state "
    "machine is deterministic.",
    "agentcore source",
    ["task_lifecycle"],
)


# ============================================================
# ADDITIONAL EXECUTION
# ============================================================

_add(
    "How does the HermesRuntime parse tool calls from runtime output?",
    "The HermesRuntime uses the TOOL_CALL_PATTERN regex in "
    "agentcore/runtimes/hermes.py to parse tool calls from the Hermes "
    "CLI's stdout. The pattern matches lines starting with 'TOOL_CALL:' "
    "followed by a JSON object. The _parse_response() method scans "
    "output line by line, extracts matching tool calls, and returns "
    "them as ToolCall objects. Parsed tool calls include structured "
    "arguments passed to ToolManager.execute().",
    "agentcore source",
    ["execution", "runtime"],
)


# ============================================================
# ADDITIONAL EVENTS
# ============================================================

_add(
    "How does the ObservationCollector handle events lacking correlation IDs?",
    "The ObservationCollector handles events without correlation IDs "
    "by using sensible fallbacks. session_id defaults to the event's "
    "session or a generated UUID. task_id falls back to session_id or "
    "empty string. turn_id defaults to a generated UUID. The "
    "ObservationCollector always generates a unique observation.id "
    "via uuid4(). This ensures every observation is traceable.",
    "agentcore source",
    ["events"],
)


# ============================================================
# ADDITIONAL FAILURE HANDLING
# ============================================================

_add(
    "How does AgentCore prevent cascading failures across components?",
    "AgentCore prevents cascading failures through failure isolation at "
    "multiple boundaries. HermesRuntime catches subprocess exceptions "
    "and returns structured RuntimeResponse objects. MemoryManager "
    "wraps all operations in try/except. The MemoryHarvester catches "
    "extraction and persistence errors individually. The "
    "ObservationCollector catches event handling exceptions. The "
    "TaskRegistry's _emit() catches EventBus errors. Each component "
    "fails independently without affecting others.",
    "agentcore source",
    ["failure_handling", "runtime"],
)


# ============================================================
# ADDITIONAL EXTENSIBILITY
# ============================================================

_add(
    "How does the EventBus subscription system work in AgentCore?",
    "The EventBus in agentcore/events.py uses a simple subscriber model. "
    "Subscribers register via event_bus.subscribe(callback). The "
    "emit() method iterates all subscribers, calling each with the "
    "AgentEvent. If a subscriber raises, it is caught and logged. The "
    "EventBus is synchronous. The subscriber_count property returns the "
    "number of registered subscribers.",
    "agentcore source",
    ["extensibility", "events"],
)


# ============================================================
# ADDITIONAL MEMORY — final batch for regression fix
# ============================================================

_add(
    "How does the MemoryHarvester handle events from the EventBus?",
    "The MemoryHarvester subscribes to the EventBus for relevant events. "
    "It listens for TASK_COMPLETED, TASK_FAILED, TOOL_CALL_COMPLETED, "
    "RUNTIME_ERROR, and other event types. When an event is received, "
    "the harvester creates an Observation from it. The harvester then "
    "applies extraction rules based on the observation type, producing "
    "MemoryCandidate objects that are persisted to the MemoryBackend "
    "with confidence levels.",
    "agentcore source",
    ["memory", "events"],
)

_add(
    "How does AgentCore's memory system recover from database corruption?",
    "AgentCore's memory system handles database corruption through the "
    "MemoryManager's try/except pattern. If the DBObsidianBackend's "
    "SQLite database is corrupted, the backend's methods raise "
    "exceptions. The MemoryManager catches these, logs warnings, emits "
    "memory.error events, and returns empty lists or None. The agent "
    "continues without memory. On the next operation, the "
    "DBObsidianBackend may attempt to re-bootstrap the database via "
    "Database.bootstrap(). If that also fails, memory remains "
    "disabled for the session.",
    "agentcore source",
    ["memory", "failure_handling"],
)

_add(
    "How does AgentCore handle memory storage with different importance levels?",
    "AgentCore's MemoryManager accepts an importance parameter "
    "(default 0.5) in store() and store_task_result(). Higher importance "
    "means the memory is more prominent in search results. The "
    "InMemoryBackend stores importance and sorts search results by "
    "importance descending. The DBObsidianBackend stores importance "
    "in the memory record. Convenience methods set specific importance "
    "levels: store_decision uses 0.8, store_lesson uses 0.7, "
    "store_project_architecture uses 0.9, store_task_result uses "
    "0.7 for success or 0.3 for failure.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore's memory observability help with debugging?",
    "AgentCore's memory observability helps debugging through: (1) "
    "EventBus events — memory.recall.started/completed carry "
    "result_count, duration, and success; memory.store.started/"
    "completed carry memory_id and duration; memory.error carries "
    "operation, error, and duration. (2) Log messages — warnings "
    "for backend failures, debug for harvester issues. (3) The "
    "MemoryContextData.to_dict() includes count and top 10 results "
    "for context inspection. (4) The DBObsidianBackend exposes "
    "provenance fields (source, confidence, origin) for tracing memory "
    "lineage. These enable debugging memory issues without code changes.",
    "agentcore source",
    ["memory", "events"],
)


# ============================================================
# FINAL ADDITIONS — reach 150+ with coverage balance
# ============================================================

_add(
    "How does AgentCore ensure memory operations never crash the agent?",
    "AgentCore ensures memory operations never crash the agent through "
    "the MemoryManager's comprehensive error handling. Every backend "
    "method call is wrapped in try/except. On failure, the manager "
    "logs a warning, emits a memory.error event, and returns a safe "
    "default (empty list for search, None for store/get/update, False "
    "for delete, 0 for clear). The enabled property short-circuits "
    "all operations when no backend is configured. This design means "
    "database corruption, locked files, network issues, or missing "
    "dependencies cannot crash the orchestrator — memory silently "
    "degrades to no-op behavior.",
    "agentcore source",
    ["memory", "safety"],
)

_add(
    "What is the role of the MemoryType enum in AgentCore's memory architecture?",
    "The MemoryType enum categorizes memories so the system can filter "
    "and retrieve specific types. TASK memories store task outcomes, "
    "PROJECT memories store architecture facts, FACT memories capture "
    "general observations, ERROR memories record failures, DECISION "
    "memories store important choices, LEARNING memories capture lessons, "
    "PREFERENCE memories store user settings, and OUTCOME memories track "
    "task completion status. The backend.list() and search() methods "
    "can filter by type, allowing the system to retrieve only relevant "
    "categories (e.g. only FACT memories for code conventions).",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore handle memory import/export for migration?",
    "AgentCore's MemoryBackend interface provides get(), list(), and "
    "search() methods that enable memory migration. A migration tool "
    "can call list() on a source backend to enumerate all memories, "
    "then call store() on a target backend to persist them. The "
    "content_hash in each record enables deduplication on the target. "
    "The provenance fields (source, confidence, origin) are preserved "
    "through _memory_to_dict() on DBObsidianBackend, ensuring "
    "lineage is maintained across backend migrations. This allows "
    "moving from InMemoryBackend to DBObsidianBackend without data loss.",
    "agentcore source",
    ["memory", "persistence"],
)

_add(
    "How does AgentCore ensure memory does not grow unbounded over time?",
    "AgentCore bounds memory growth through several mechanisms: (1) "
    "max_context_records (default 10) limits how many memories are "
    "returned from a single search, enforced by min(limit, "
    "self._max_context_records); (2) max_content_chars (default 2000) "
    "truncates individual memory content; (3) the MemoryHarvester "
    "filters low-information candidates via _is_low_information(); "
    "(4) DB-Obsidian's deduplication prevents identical content from "
    "accumulating; (5) the InMemoryBackend has no automatic eviction "
    "but is not used in production; (6) memory.delete() and clear() "
    "allow explicit cleanup. However, there is no automatic TTL or "
    "aging mechanism in the current implementation.",
    "agentcore source",
    ["memory", "safety"],
)

_add(
    "How does AgentCore handle the difference between memory importance and confidence?",
    "AgentCore distinguishes importance from confidence in memory storage. "
    "Importance (0.0-1.0, default 0.5) reflects how central the memory is "
    "to the task — higher importance means more relevant. The "
    "InMemoryBackend sorts search results by importance descending. "
    "Confidence (0.0-1.0, via MemoryConfidence enum) reflects how "
    "trustworthy the memory is — VERIFIED=1.0, CLAIMED=0.7, INFERRED=0.5, "
    "UNKNOWN=0.3. Confidence is used by the MemoryHarvester for "
    "monotonic upgrades and by the backend's min_confidence filtering. "
    "Importance affects search ranking; confidence affects memory quality.",
    "agentcore source",
    ["memory"],
)

_add(
    "How does AgentCore's memory system interact with the VERIFYING task state?",
    "During the VERIFYING state, the OrchestrationEngine uses memory to "
    "validate task completion. It calls MemoryManager.search() with "
    "queries related to the task requirements to find past attempts, "
    "known issues, or verification criteria. The MemoryManager."
    "retrieve_relevant_memory() method is called by the agent to "
    "gather verification context. If the memory contains evidence of "
    "past failures for similar tasks, the agent can flag incomplete "
    "verification. After verification, the task transitions to "
    "COMPLETED (with the result stored as a TASK memory) or back to "
    "REPLANNING if verification fails.",
    "agentcore source",
    ["memory", "task_lifecycle"],
)

_add(
    "How does AgentCore handle memory when switching between skills during execution?",
    "When the OrchestrationEngine switches skills during execution (via "
    "the REPLANNING state), it retrieves memories relevant to the new "
    "skill context. The MemoryManager.search() is called with a query "
    "derived from the new skill's purpose and the task context. Memories "
    "tagged with the previous skill's project context may be excluded "
    "via project filtering. The retrieved memories are embedded in the "
    "context dict for the new runtime call. This ensures the agent "
    "doesn't lose context when switching between different skill "
    "approaches to the same problem.",
    "agentcore source",
    ["memory", "routing", "orchestration"],
)

_add(
    "What memory-related events does AgentCore's MemoryManager emit during normal operation?",
    "During normal operation, the MemoryManager emits several event types: "
    "(1) memory.recall.started — when search() begins, with query and "
    "project in metadata; (2) memory.recall.completed — after search(), "
    "with result_count, duration, and success flag; (3) memory.store."
    "started — when store() begins, with type and project; (4) "
    "memory.store.completed — after store(), with memory_id, duration, "
    "and success; (5) memory.error — on any backend failure, with "
    "operation, error, and duration. These events enable external "
    "observers to monitor memory activity in real time.",
    "agentcore source",
    ["memory", "events"],
)

_add(
    "How does AgentCore's memory system support the INVESTIGATING task state?",
    "During the INVESTIGATING state, the OrchestrationEngine uses memory "
    "to gather context before planning. It calls "
    "MemoryManager.retrieve_relevant_memory() with the user's original "
    "request as the query, scoped to the current project. The returned "
    "memories may include past project architectures (PROJECT type), "
    "similar task outcomes (TASK type), relevant facts (FACT type), or "
    "important decisions (DECISION type). This context enriches the "
    "planning phase by providing historical knowledge. If memory is "
    "unavailable, the INVESTIGATING phase proceeds with only the "
    "project's filesystem context.",
    "agentcore source",
    ["memory", "task_lifecycle", "orchestration"],
)


# ============================================================
# ADDITIONAL ARCHITECTURE EXAMPLES
# ============================================================

_add(
    "How does AgentCore enforce the principle of separation between decision and execution layers?",
    "AgentCore enforces separation between decision (orchestration) and "
    "execution (runtime) layers through the RuntimeAdapter abstract "
    "interface. The orchestration layer (agent.py, task_registry.py) "
    "contains all decision logic: planning, routing, state management, "
    "memory retrieval. It calls RuntimeAdapter.respond() to delegate "
    "execution but never accesses runtime internals. The runtime "
    "adapter (e.g. HermesRuntime) contains all execution logic: "
    "subprocess management, prompt building, output parsing. It "
    "returns only a structured RuntimeResponse. This strict interface "
    "boundary ensures layer independence.",
    "agentcore source",
    ["architecture", "runtime_adapter"],
)

_add(
    "What design principle does AgentCore follow for dependency management?",
    "AgentCore follows the dependency inversion principle: high-level "
    "modules (orchestration) define abstract interfaces, and low-level "
    "modules (runtimes, backends) implement them. The orchestration "
    "layer depends on RuntimeAdapter, MemoryBackend, and "
    "ObservationStore abstractions — never on concrete implementations. "
    "Concrete implementations are injected at construction time and "
    "selected via registries (RuntimeRegistry, etc.). This allows "
    "third parties to provide alternative implementations without "
    "modifying the orchestration layer.",
    "agentcore source",
    ["architecture", "extensibility"],
)


# ============================================================
# ADDITIONAL CANCELLATION
# ============================================================

_add(
    "How does AgentCore ensure cancellation is propagated even if the runtime is busy?",
    "AgentCore ensures cancellation propagation through a dual mechanism. "
    "The OrchestrationEngine sets the task state to CANCELLED "
    "synchronously via the TaskRegistry, which force-releases the "
    "task lock. Simultaneously, it calls "
    "RuntimeAdapter.cancel() on the active runtime. For HermesRuntime, "
    "cancel() sets a _cancelled flag and terminates the subprocess. "
    "Even if the runtime is blocked (e.g. subprocess timeout), the "
    "process.terminate() call interrupts it. The _cancelled flag "
    "ensures that even if respond() is still processing, the next "
    "call returns FinishReason.CANCELLED.",
    "agentcore source",
    ["cancellation", "runtime"],
)


# ============================================================
# ADDITIONAL SHUTDOWN
# ============================================================

_add(
    "What happens to memory data during AgentCore shutdown?",
    "During AgentCore shutdown, the MemoryManager.close() method is "
    "called, which closes the DBObsidianBackend's SQLite connection. "
    "Before close(), any pending memory operations (store, "
    "update_confidence) are allowed to complete through the backend's "
    "transaction handling. The SQLite database may be in WAL mode, "
    "so a checkpoint may be needed. The MemoryManager does not perform "
    "explicit flushing before close — it relies on SQLite's "
    "transaction durability. If the backend is InMemoryBackend, "
    "close() is a no-op and all in-memory data is lost.",
    "agentcore source",
    ["shutdown", "memory"],
)


# ============================================================
# ADDITIONAL FAILURE HANDLING
# ============================================================

_add(
    "How does AgentCore ensure errors are not silently swallowed?",
    "AgentCore does not swallow errors silently — it catches them at "
    "the appropriate boundary and converts them to structured responses "
    "or logged warnings. Runtime exceptions in HermesRuntime.respond() "
    "become RuntimeResponse with FinishReason.ERROR. Memory backend "
    "failures are caught in MemoryManager and logged as warnings, "
    "emitted as memory.error events. Persistence failures are logged "
    "and emitted as events. The ObservationCollector logs extraction "
    "errors at debug level. This design ensures errors are visible "
    "(logged + events) but never crash the agent. The key principle: "
    "fail gracefully at the boundary, never propagate unhandled "
    "exceptions.",
    "agentcore source",
    ["failure_handling"],
)


# ============================================================
# V3 REGRESSION FIX — safety: resource limits
# ============================================================

_add(
    "What resource limits does AgentCore apply to running tasks?",
    "AgentCore applies resource limits through AgentConfig: max_iterations "
    "(default 10), max_tool_calls (default 50), max_runtime_seconds (default 300), "
    "and timeout (default 300s). The OrchestrationEngine checks these limits "
    "during the agent loop. The HermesRuntime enforces timeout via "
    "subprocess.communicate(timeout=self.timeout). If exceeded, TimeoutExpired "
    "is caught, _cancel_in_flight() terminates the subprocess, and "
    "FinishReason.TIMEOUT is returned.",
    "agentcore source",
    ["safety", "runtime"],
)

_add(
    "How does HermesRuntime handle a runtime timeout?",
    "When HermesRuntime's subprocess exceeds the configured timeout, "
    "TimeoutExpired is caught and _cancel_in_flight() terminates the process "
    "via process.terminate(), escalating to process.kill() if it does not "
    "exit within 5 seconds. The OrchestrationEngine receives "
    "FinishReason.TIMEOUT and can retry (max_replans default 3) or transition "
    "to FAILED. This prevents runaway execution.",
    "agentcore source",
    ["safety", "runtime", "cancellation"],
)

# ============================================================
# V3 REGRESSION FIX — safety: security boundaries
# ============================================================

_add(
    "How are security boundaries maintained between runtime adapters?",
    "AgentCore maintains security boundaries through process isolation. "
    "Each runtime adapter runs in its own subprocess via HermesRuntime.spawn(). "
    "The orchestration layer communicates only through the RuntimeAdapter "
    "interface — adapters cannot access MemoryBackend, TaskRegistry, or "
    "ObservationStore directly. Process-level isolation ensures runtimes have "
    "separate memory spaces and cannot inspect each other's state. A runtime "
    "crash is contained within its subprocess boundary by the OS.",
    "agentcore source",
    ["safety", "runtime", "runtime_adapter"],
)

_add(
    "Do runtimes share memory or state in AgentCore?",
    "No — runtimes in AgentCore are strictly isolated by process boundaries. "
    "Each runtime adapter operates in its own subprocess with its own memory "
    "space. The orchestration layer communicates with runtimes exclusively "
    "through the RuntimeAdapter interface (respond(), capabilities(), cancel()). "
    "A runtime has no direct function calls or memory access to other runtimes "
    "or the orchestrator's internal state. Any data sharing must go through "
    "the orchestration layer, which applies appropriate filtering and "
    "isolation guarantees.",
    "agentcore source",
    ["safety", "runtime", "orchestration"],
)

# ============================================================
# V3 REGRESSION FIX — events: runtime event propagation
# ============================================================

_add(
    "How does HermesRuntime propagate completion events to the orchestration layer?",
    "HermesRuntime propagates completion events through the "
    "ObservationCollector and EventBus. After a RuntimeResponse is parsed, "
    "_emit() creates AgentEvent objects with structured data (event type, "
    "task_id, iteration, outcome). The ObservationCollector subscribes to "
    "these events and translates them into Observations with stable "
    "correlation IDs (observation.id, session_id, task_id, turn_id). These "
    "Observations are stored in the ObservationStore for retrieval by the "
    "MemoryHarvester. The EventBus propagates events synchronously to "
    "subscribed observers, carrying typed event data for state transitions "
    "and monitoring.",
    "agentcore source",
    ["events", "runtime_adapter", "events"],
)

_add(
    "What event types does HermesRuntime emit on task completion?",
    "HermesRuntime emits the following event types on task completion: "
    "TOOL_CALL_COMPLETED (if tool calls were executed), RUNTIME_ERROR "
    "(if the runtime failed), TASK_COMPLETED (if the task succeeded), or "
    "TASK_FAILED (if the task failed). Each event carries metadata "
    "including task_id, iteration, and outcome data. The "
    "ObservationCollector correlates these events to observations using "
    "deterministic correlation IDs, enabling the MemoryHarvester to extract "
    "memory candidates from the task's execution history.",
    "agentcore source",
    ["events", "task_lifecycle", "runtime"],
)

# ============================================================
# V3 REGRESSION FIX — execution: resource limits during delegation
# ============================================================

_add(
    "How does execution delegation work when a runtime is selected?",
    "When AgentCore delegates execution to a runtime adapter, the "
    "orchestration layer builds a context dict and calls "
    "RuntimeAdapter.respond(context). The runtime adapter formats the context "
    "into a prompt, invokes the backend, and parses the response. Resource "
    "limits (max_iterations, max_tool_calls, max_runtime_seconds, timeout) "
    "are checked by the OrchestrationEngine before and during execution. "
    "If a runtime exceeds its timeout, TimeoutExpired is caught and the "
    "subprocess is terminated. The OrchestrationEngine then checks "
    "max_replans and either retries or transitions the task to FAILED. "
    "This ensures execution delegation operates within bounded resource "
    "constraints.",
    "agentcore source",
    ["execution", "runtime", "safety"],
)

_add(
    "What resource guards prevent unbounded consumption during execution delegation?",
    "AgentCore uses multiple defense-in-depth layers to prevent "
    "unbounded resource consumption. The OrchestrationAgentConfig enforces "
    "max_iterations (default 10), max_tool_calls (default 50), "
    "max_runtime_seconds (default 300), and timeout (default 300s). The "
    "HermesRuntime enforces process-level timeouts via "
    "subprocess.communicate(timeout=). If the timeout is exceeded, the "
    "process is terminated. The OrchestrationEngine monitors finish_reason "
    "and can retry (up to max_replans) or fail the task. The ToolManager "
    "also limits individual tool call execution, maintaining resource "
    "guards throughout the agent loop.",
    "agentcore source",
    ["execution", "safety", "runtime_adapter"],
)


def get_all_experiences() -> list[Experience]:
    """Return all training candidates as Experience objects.

    CorrectionPair objects are expanded into their correct-answer Experience
    form (the wrong answers are metadata, not standalone training examples).
    """
    experiences: list[Experience] = list(TRAINING_CANDIDATES)

    for pair in CORRECTION_CANDIDATES:
        experiences.append(pair.to_experience_correct())

    return experiences
