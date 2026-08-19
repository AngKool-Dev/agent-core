# AgentCore V0.1 Architecture

## Overview

AgentCore is a universal AI coding-agent framework with pluggable runtime adapters.

## Core Components

```
                    USER
                     │
                     ▼
              ┌─────────────┐
              │  AgentCore  │
              └──────┬──────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Context     Skills     Memory
          │          │          │
          └──────────┼──────────┘
                     ▼
                  Planner
                     │
                     ▼
              Runtime Adapter
                     │
                     ▼
                  Hermes
```

## Key Design Principles

1. **Runtime Independence**: The agent brain is separate from the runtime.
2. **Pluggable Architecture**: New runtimes (Kilo, OpenCode) can be added without changing core.
3. **Skill Composition**: Skills are discovered and composed automatically.
4. **Structured State**: All task state is serializable for persistence.
5. **Investigation-First**: The agent investigates before acting.

## Components

### Task Model
- Structured representation of agent work
- Serializable state transitions
- Hypothesis tracking
- Verification state

### Skill System
- Discovers skills from configurable directories (project-local, user-level, or via `AGENTCORE_SKILLS_PATH` env var)
- Automatic routing based on prompt analysis
- Supports multiple skills per task

### Memory
- Abstract interface (`MemoryManager`)
- DB-Obsidian adapter available (see `docs/memory.md`)
- InMemoryBackend for testing and default operation
- Project and session persistence

See `docs/memory.md` for the full memory architecture and confidence model.

### Runtime Adapter
- Abstract interface (`RuntimeAdapter`)
- Hermes implementation (`HermesRuntime`)
- Pluggable for Kilo, OpenCode

### Verifier
- Project-type aware checks
- Format, build, and test verification
- Failure classification
- Verification scope controls which files are considered for file-scoped checks, while check flags control which checks run at all

#### Verification Scope vs Check Scope

AgentCore distinguishes between two orthogonal concepts:

| Concept | Controls | Values |
|---|---|---|
| **Verification scope** | Which files are in scope for file-scoped checks | `"project"` (default), `"changed-files"` |
| **Check scope** | Which verification checks are enabled | `run_format_check`, `run_build_check`, `run_tests` |

**Verification scope** determines the set of files a check operates against:
- `"project"`: checks run against the entire repository (default)
- `"changed-files"`: checks run only against files changed during the task, computed as the delta from the task-start Git state

**Check scope** determines which checks execute:
- `run_format_check`: format/lint check
- `run_build_check`: build/compile check
- `run_tests`: test suite

Under `"changed-files"` scope, only the **format check** is file-scoped. Build and test checks remain project-wide because they validate repository-wide correctness. The `git diff --check` check always validates the entire repository for whitespace errors regardless of scope.

If Git is unavailable or snapshot capture fails, the verifier falls back to project-wide verification rather than silently skipping checks.

## Directory Structure

```
agent-core/
├── agentcore/
│   ├── __init__.py          # Public API exports
│   ├── agent.py             # Main agent orchestrator
│   ├── agentcore.py         # AgentCore facade (lifecycle, persistence, limits)
│   ├── task.py              # Task model and state machine
│   ├── planner.py           # Plan generation and adaptation
│   ├── router.py            # Skill routing
│   ├── context.py           # Project context discovery
│   ├── memory.py            # Memory abstraction (Manager, Backend, Record)
│   ├── verifier.py          # Verification system
│   ├── tools.py             # Tool execution
│   ├── config.py            # Configuration loading and typed config
│   ├── control.py           # Control plane (cancellation, limits)
│   ├── desktop_task_coordinator.py  # Hermes task coordination
│   ├── harvesting.py        # Memory harvesting from observations
│   ├── observations.py      # Observation store and collector
│   ├── events.py            # Event bus
│   ├── persistence.py       # Task persistence (filesystem + in-memory)
│   ├── runtimes/            # Runtime adapters
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract runtime interface
│   │   ├── hermes.py        # Hermes implementation
│   │   └── registry.py      # Runtime registry
│   ├── adapters/            # Optional adapters
│   │   ├── memory_dbobsidian.py      # DB-Obsidian memory backend
│   │   ├── hermes_event_bridge.py  # Hermes Desktop event bridge
│   │   └── obsidian_observation_store.py  # DB-Obsidian observation store
│   ├── skills/              # Skill system
│   │   ├── __init__.py
│   │   ├── loader.py        # Skill content loader
│   │   └── registry.py      # Skill discovery and registry
│   ├── cli/                 # CLI (agent + argus)
│   │   ├── __init__.py
│   │   ├── main.py          # Entry points: agent, argus
│   │   ├── service.py       # QueryService assembly
│   │   ├── utils.py         # CLI utilities
│   │   └── commands/        # Subcommand handlers
│   │       ├── __init__.py
│   │       ├── task.py
│   │       └── memory.py
│   └── training/            # Training data pipeline
│       ├── __init__.py
│       ├── analyzer.py      # ExperienceAnalyzer
│       ├── build.py         # build_dataset CLI
│       ├── candidates.py    # 158 learning candidates
│       ├── dataset.py       # DatasetBuilder + quality gate
│       ├── domains.py       # 15-domain classification
│       ├── experience.py    # Experience dataclass
│       ├── leakage.py       # Eval leakage detection
│       ├── scorer.py        # QualityScorer (5-axis)
│       └── stats.py         # DatasetStats CLI
├── tests/                   # Test suite (unit + integration)
│   ├── training/            # Training pipeline tests (98 tests)
│   ├── integration/         # Cross-component integration tests
│   └── real_runtime/        # Hermes-dependent tests (opt-in)
├── config/
│   └── agent.toml           # Default configuration template
├── docs/
│   ├── architecture.md      # This file
│   ├── cli-reference.md     # Argus CLI reference
│   ├── hermes-integration.md
│   ├── memory.md
│   └── runtime-adapters.md
├── examples/                # Usage examples
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── pyproject.toml
```

## Task Lifecycle

```
                    start_task()
                         │
                         ▼
                ┌─────────────────┐
                │  TaskRegistry   │ ← tracks active tasks
                └────────┬────────┘
                         │
                         ▼
              ┌──────────────────┐
              │     Planner      │ ← generates hypotheses + plan
              └────────┬─────────┘
                       │
           ┌───────────┼───────────┐
           │  investigate         │  implement
           ▼                       ▼
    ┌─────────────┐        ┌─────────────┐
    │  ToolManager │        │  ToolManager │
    │  (read tools) │        │  (write tools)│
    └─────────────┘        └─────────────┘
           │                       │
           └──────────┬───────────┘
                      │
                      ▼
              ┌──────────────────┐
              │ RuntimeAdapter   │ ← execute plan
              └────────┬─────────┘
                       │
                       ▼
                ┌────────────┐
                │Verifier    │ ← format/build/test checks
                └────────────┘
                       │
                       ▼
                ┌────────────┐
                │TaskRegistry│ ← complete/failed
                └────────────┘
```

## Data Flow

```
AgentCore
   │
   ├── EventBus ──────────────► ObservationCollector ──► ObservationStore
   │                                          │
   │                                          ▼
   │                                  MemoryHarvester ──► MemoryBackend
   │
   └── TaskPersistence ──► FilesystemPersistenceBackend
```

AgentCore does not introduce its own database. Task persistence uses the
filesystem (JSON files per task). Memory and observations use db-obsidian when
available, falling back to in-memory backends.

## CLI Architecture

```
┌──────────┐    ┌──────────────┐    ┌──────────────────┐
│  agent   │    │   argus       │    │   QueryService    │
│  CLI     │    │   CLI        │    │   (read-only)     │
└──────────┘    └──────────────┘    └──────────────────┘
     │                  │                      │
     └── main()         └── main()             ├── TaskRegistry
           │                   │                ├── ObservationStore
           ▼                   ▼                └── MemoryBackend
      AgentCore             create_query_service()
```

- `agent` — Runs an AI coding agent (requires a runtime adapter)
- `argus` — Observes and queries persisted state (no runtime required)