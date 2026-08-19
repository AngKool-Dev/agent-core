# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-19

### Added
- Initial public framework release
- **AgentCore** orchestration facade with task lifecycle management,
  resource limits, graceful shutdown, and event emission
- **Runtime adapter architecture** — `RuntimeAdapter` abstract interface with
  `RuntimeResponse` contract and `RuntimeCapabilities` standardized keys
  (`text_generation`, `tool_calls`, `external_tool_execution`, `streaming`,
  `cancellation`)
- **Hermes runtime** (`HermesRuntime`) — integration with Hermes Desktop CLI
  via `hermes -z` one-shot mode; black-box text runtime with subprocess
  cancellation
- **Hermes Desktop integration** — `HermesEventBridge` for event listening,
  `DesktopTaskCoordinator` for task registration, `HermesControlBridge` for
  outbound control signals
- **Task lifecycle** — state machine with `DRAFTED` → `INVESTIGATING` →
  `IMPLEMENTING` → `VERIFYING` → `COMPLETED`/`FAILED`/`CANCELLED` transitions,
  persistent to filesystem
- **Verification system** — project-type aware format/build/test checks with
  scope control (`"project"` / `"changed-files"`) and Git delta tracking
- **Skill system** — discovery from configurable paths, prompt-based routing
- **Memory architecture** — `MemoryManager`, `MemoryBackend` abstraction with
  `InMemoryBackend` (default) and optional `DBObsidianBackend`
- **Memory harvesting** — `MemoryHarvester` extracts memory candidates from
  observations with deterministic IDs (SHA-256) and confidence levels
  (`UNKNOWN` 0.3, `INFERRED` 0.5, `CLAIMED` 0.7, `VERIFIED` 1.0)
- **Observation system** — `ObservationCollector` and `ObservationStore` with
  in-memory and DB-Obsidian implementations
- **Tool execution framework** — `ToolManager` with file read/write/search tools
- **Event bus** — local `EventBus` with publish/subscribe
- **Persistence** — filesystem-based task persistence with `TaskPersistenceManager`
- **Argus CLI** — read-only observability CLI for tasks, events, and memory
  (`argus task list/show/events/memories`, `argus memory search/show/confidence`)
- **Training data pipeline** — `agentcore.training` module with
  `LeakageDetector` (4-check eval leakage prevention), `QualityScorer`
  (5-axis deterministic scoring), `DatasetBuilder` (quality gate with
  secret/PII detection), and `build_dataset` CLI
- **Training dataset v016** — 158 examples (150 successes + 8 correction pairs),
  0 evaluation leakage, 0 duplicates
- **Cross-platform CI** — GitHub Actions workflow testing on
  Ubuntu/Windows/macOS × Python 3.11/3.12
- **Packaging** — wheel and sdist via `python -m build`, `py.typed` marker,
  zero required runtime dependencies (`db-obsidian` available from GitHub source,
  with graceful `InMemoryBackend` fallback)
- **Graceful degradation** — AgentCore functions without Hermes,
  without db-obsidian, and without any optional packages installed

### Changed
- Public API surface defined in `agentcore/__init__.py` with explicit `__all__`
- Default `memory_backend` changed from `"db_obsidian"` to `"in_memory"`
  (db-obsidian is now opt-in, not default)
- Package metadata and distribution configuration in `pyproject.toml`
- `.gitignore` updated to exclude test artifacts (`MagicMock/`, `*.db`,
  `*.log`, `.kilo/`)

### Deprecated
- None

### Removed
- None

### Fixed
- Hard-coded `C:\EraAI` paths replaced with configurable `EPOCH_EVAL_PATH`
  environment variable in training pipeline
- Project-wide Ruff lint violations (unused imports, ambiguous variable names,
  line length, type annotations) resolved across 79+ files
- `Agent` import preserved in `agentcore/cli/main.py` with `# noqa: F401`
  for test compatibility

### Security
- Subprocess invocations audited for portability (no `shell=True`)
- No secrets, API keys, or credentials in repository
- No machine-specific paths in core code
- Zero required dependencies (all optional packages are truly optional)

### Known Limitations
- **db-obsidian** is not auto-installed. Users must install manually
  (`pip install db-obsidian`) for persistent memory
- Memory confidence classification is rule-based, not learned
- `InMemoryBackend` does not persist across process restarts
- Memory eviction/promotion not implemented in v0.1.0
- Cross-project memory search not supported
- v0.1.0 is a **framework release**, not a turnkey product
- Hermes Desktop integration requires a running Hermes Desktop session
