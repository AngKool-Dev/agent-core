# AgentCore

**Runtime-agnostic orchestration layer for AI coding agents.**

AgentCore is **not** Hermes, Kilo, OpenCode, Claude Code, or any other AI coding agent.
It is the orchestration layer that sits *above* them:

```
                    ┌─────────────────────────┐
                    │       AGENTCORE          │
                    │  Universal Orchestration │
                    │          Layer            │
                    ├─────────────────────────┤
                    │  Task Lifecycle            │
                    │  EventBus                  │
                    │  Observations              │
                    │  Memory Harvesting         │
                    │  Confidence Scoring        │
                    │  Persistence               │
                    │  Runtime Adapters          │
                    └────────────┬────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
         ┌────────┐          ┌────────┐          ┌──────────┐
         │ Hermes │          │  Kilo  │          │ OpenCode │
         └────────┘          └────────┘          └──────────┘
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 ▼
                      Persistent Memory (DB-Obsidian)
```

Plug in any coding agent runtime — Hermes today, Kilo and OpenCode tomorrow —
without changing AgentCore's logic. AgentCore handles task lifecycle,
memory, verification, and orchestration so your runtime doesn't have to.

---

## Why AgentCore?

| You have this... | AgentCore gives you... |
|---|---|
| A coding agent that manages tasks, memory, and verification | A clean separation: your runtime does the language model calls, AgentCore does everything else |
| Hardcoded task persistence and memory logic in your CLI | Swappable backends (in-memory for testing, DB-Obsidian for production) |
| No cross-session memory consolidation | Deterministic memory harvesting with confidence scoring |
| No observability layer | `argus` CLI for inspecting tasks, observations, and memories |
| No standardized runtime interface | `RuntimeAdapter` contract with capability flags |

AgentCore is the orchestration layer that makes any coding agent production-ready.

---

## Quick Start

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Linux/macOS:
source .venv/bin/activate

# Install AgentCore — zero required dependencies
pip install agentcore

# Run a task (requires Hermes — see below)
agent "Fix the launcher crash"

# Inspect results without a runtime
argus task list
```

> **Python 3.11+** is required. AgentCore has **no required dependencies**.
> Runtimes, memory backends, and tools are optional and loaded lazily.

### What's installed

| Command | Description |
|---|---|
| `agent` | Run an AI coding agent (requires a runtime adapter) |
| `argus` | Read-only observability CLI — works without any runtime |

---

## First Time Running a Task

With Hermes Desktop installed:

```bash
# Run a task against the current project
agent "Why does the login handler fail on edge cases?"

# Target a specific project
agent -p /path/to/project "Implement pagination in the results view"

# Choose a model
agent -r hermes -m claude-sonnet-4 "Refactor the auth module"

# List installed runtimes
agent --list-runtimes
```

AgentCore will:
1. Discover project context (language, files, structure)
2. Plan the task (investigate → implement → verify)
3. Delegate to the Hermes runtime for language model calls
4. Harvest memories with confidence scoring
5. Verify results with format/build/test checks
6. Persist everything for later inspection via `argus`

---

## Architecture

```
                USER
                 │
                 ▼
        ┌──────────────┐
        │   AgentCore   │   ← Task lifecycle, persistence, limits
        └──────┬───────┘
               │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
Context    Skills     Memory
   │          │          │
   └──────────┼──────────┘
              ▼
          Planner
              │
              ▼
       Runtime Adapter    ← Hermes, Kilo, OpenCode
              │
              ▼
            Hermes
```

### Layer table

| Layer | Responsibility |
|---|---|
| **AgentCore** | Task lifecycle (state machine), persistence, resource limits, graceful shutdown |
| **Context** | Project context discovery (language type, file inventory, exclude patterns) |
| **Skills** | Skill discovery from filesystem, prompt-based routing |
| **Memory** | Optional memory storage (InMemoryBackend default, DB-Obsidian adapter optional) |
| **Planner** | Plan generation and replanning |
| **Runtime Adapter** | Abstract interface to LLM runtimes (Hermes, Kilo, OpenCode) |
| **Verifier** | Post-completion verification (format, build, tests) with scope control |
| **Argus** | Read-only CLI for inspecting tasks, observations, and memory |

### Data flow

```
AgentCore
   │
   ├── EventBus ──────────► ObservationCollector ──► ObservationStore
   │                              │
   │                              ▼
   │                      MemoryHarvester ──► MemoryBackend
   │
   └── TaskPersistence ──► FilesystemPersistenceBackend
```

AgentCore does **not** introduce its own database. Task persistence is filesystem-based
(JSON per task). Memory and observations use DB-Obsidian when available, falling back
to in-memory backends.

---

## Runtimes

AgentCore supports multiple runtimes through the `RuntimeAdapter` interface. Runtimes
are **lazy** — they are not imported or required at install time.

### Capability contract

Runtimes declare what they support via `capabilities()`:

| Key | Meaning |
|---|---|
| `text_generation` | Runtime can produce text responses |
| `tool_calls` | Runtime exposes structured `ToolCall` objects to AgentCore |
| `external_tool_execution` | AgentCore executes those tools via `ToolManager` |
| `streaming` | Runtime supports streaming responses |
| `cancellation` | Runtime supports cancellation |

### Two runtime categories

| Runtime type | `tool_calls` | `external_tool_execution` | Behavior |
|---|---|---|---|
| **Tool-aware** | `true` | `true` | AgentCore executes tools, observes results |
| **Black-box** | `false` | `false` | Runtime handles tools internally |

Hermes v0.20+ in `-z` mode is a black-box runtime — AgentCore sees
`tool_calls=[]` and skips the tool-execution state machine.

### Built-in: Hermes Runtime

```python
from agentcore import HermesRuntime

runtime = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
response = runtime.respond({"user_request": "Explain dependency injection"})
# RuntimeResponse(content="...", finish_reason=FinishReason.STOP)
```

See [`docs/runtime-adapters.md`](docs/runtime-adapters.md) for the full adapter
contract and how to integrate Kilo, OpenCode, or your own runtime.

---

## Memory & Observability

### Argus CLI (read-only, no runtime required)

```bash
# List tasks
argus task list --state running

# Show task details
argus task show hermes-abc123-task456

# Show observations/events for a task
argus task events hermes-abc123-task456 --limit 50

# Show harvested memories
argus task memories hermes-abc123-task456 --min-confidence VERIFIED

# Search memories
argus memory search "authentication error" --limit 10 --json

# Show memory confidence diagnostic
argus memory confidence mem-a1b2c3d4e5f6
```

See [`docs/cli-reference.md`](docs/cli-reference.md) for the full reference.

### Memory system

Memory is harvested from task observations with deterministic IDs and
confidence levels:

| Level | Score | Meaning |
|---|---|---|
| `UNKNOWN` | 0.3 | Inferred from observation; no explicit claim |
| `INFERRED` | 0.5 | Derived from task execution patterns |
| `CLAIMED` | 0.7 | Explicitly stated by the model |
| `VERIFIED` | 1.0 | Matches a verified tool outcome |

### Memory backends

| Backend | Persistent | Dependencies |
|---|---|---|
| `in_memory` (default) | No | None |
| `db_obsidian` | Yes (SQLite + Obsidian) | `pip install agentcore[db-obsidian]` |

If `db-obsidian` is not installed, AgentCore automatically falls back to
`InMemoryBackend`. To enable persistent memory:

```bash
pip install agentcore[db-obsidian]
```

Or from GitHub:

```bash
pip install git+https://github.com/AngKool-Dev/db-obsidian
```

See [`docs/memory.md`](docs/memory.md) for the full memory architecture and
[`docs/hermes-integration.md`](docs/hermes-integration.md) for Hermes Desktop
integration details.

---

## Installation

### From PyPI

```bash
pip install agentcore
```

### With optional extras

```bash
# Development tools (pytest, ruff, build)
pip install agentcore[dev]

# Persistent memory backend
pip install agentcore[db-obsidian]

# All extras
pip install agentcore[dev,db-obsidian]
```

### From source

```bash
git clone https://github.com/AngKool-Dev/agent-core.git
cd agent-core
pip install -e ".[dev]"
```

---

## Python API

```python
from agentcore import Agent, AgentConfig, AgentCoreConfig, create_agent, create_agent_core

# Create the AgentCore facade (task lifecycle, persistence)
core = create_agent_core(config=AgentCoreConfig(default_runtime="hermes"))

# Create an agent with a runtime and memory backend
from agentcore import HermesRuntime, MemoryManager, InMemoryBackend

runtime = HermesRuntime(model="claude-sonnet-4")
memory = MemoryManager(InMemoryBackend())
config = AgentConfig(max_iterations=10, enable_verification=True)

agent = Agent(runtime=runtime, memory=memory, config=config)
result = agent.execute("Fix the failing tests")
```

### Custom runtime

```python
from agentcore.runtimes.base import RuntimeAdapter, RuntimeResponse, FinishReason


class MyRuntime(RuntimeAdapter):
    def respond(self, context):
        return RuntimeResponse(
            content="Hello from my runtime",
            finish_reason=FinishReason.STOP,
        )

    def capabilities(self):
        return {
            "text_generation": True,
            "tool_calls": False,
            "external_tool_execution": False,
            "streaming": False,
            "cancellation": False,
        }


# Register it
from agentcore.runtimes import get_default_registry

registry = get_default_registry()
registry.register("my-runtime", lambda **kw: MyRuntime())
```

### Custom tool

```python
from pathlib import Path
from agentcore.tools import ToolManager, ToolResult


def my_tool(args: dict, work_dir: Path, start: float) -> ToolResult:
    return ToolResult(success=True, tool="my_tool", output="done")


manager = ToolManager(project_path=".")
manager.register_tool("my_tool", my_tool)
```

See `examples/` for working examples:
- `examples/basic_agent.py` — Minimal agent with an echo runtime
- `examples/custom_runtime.py` — Implementing a `RuntimeAdapter`
- `examples/custom_tool.py` — Registering a custom tool

---

## Configuration

AgentCore loads configuration from TOML files in priority order:

1. Explicit: `agent --config path/to/agentcore.toml`
2. Project-local: `./agentcore.toml` or `./config/agentcore.toml`
3. User-level: `{user_config_dir}/agentcore/agentcore.toml`
4. Built-in defaults

```toml
[agent]
default_runtime = "hermes"     # Runtime adapter to use
model = "claude-sonnet-4"      # Model override (optional)

[memory]
backend = "in_memory"          # "in_memory" or "db_obsidian"
db_path = "~/.agentcore/memory.db"

[limits]
max_iterations = 10            # Max agent loop iterations per task
max_tool_calls = 50            # Max tool calls per task
timeout = 300                  # Per-request timeout (seconds)

[verification]
run_format_check = true
run_build_check = true
run_tests = true
scope = "project"              # "project" or "changed-files"

[context]
max_context_files = 50
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run default test suite (fast, deterministic — no runtime needed)
pytest tests/ -q

# Run real-runtime tests (requires Hermes Desktop)
AGENTCORE_REAL_RUNTIME=1 pytest -m real_runtime -q
```

### Test tiers

| Tier | Runtime | Default? |
|---|---|---|
| Unit | Mocked | Yes |
| Integration | Deterministic/mock | Yes |
| Real runtime | Hermes/Kilo/OpenCode | No |

The default `pytest -q` suite runs unit and deterministic integration tests only.
Real-runtime tests are opt-in via the `AGENTCORE_REAL_RUNTIME` environment variable
and the `real_runtime` marker.

### Validation commands

```bash
# Release gate
ruff check .
ruff format --check .
pytest tests/ -q
git diff --check
python -m build
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development guidelines.

---

## Documentation

| Doc | Description |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System architecture and design |
| [`docs/cli-reference.md`](docs/cli-reference.md) | Argus CLI command reference |
| [`docs/runtime-adapters.md`](docs/runtime-adapters.md) | Runtime adapter interface and capability contract |
| [`docs/hermes-integration.md`](docs/hermes-integration.md) | Hermes Desktop integration and identity model |
| [`docs/memory.md`](docs/memory.md) | Memory harvesting, confidence, and backends |

---

## Current Limitations

- **v0.1.0 is a framework release**, not a turnkey product. Integration with Hermes
  Desktop requires a running Hermes Desktop session.
- `db-obsidian` is not auto-installed or published to PyPI. Users must install it
  from GitHub for persistent memory: `pip install git+https://github.com/AngKool-Dev/db-obsidian`
  or `pip install agentcore[db-obsidian]` (when available on PyPI).
- Memory harvesting is deterministic but minimal. Advanced memory consolidation
  (eviction, promotion, clustering) is planned for future releases.
- The verifier runs format/build/test checks but does not auto-apply fixes.
- Real-runtime tests require Hermes Desktop to be installed on the host system.
- Confidence classification is rule-based, not learned.

---

## License

MIT — see [LICENSE](LICENSE).
