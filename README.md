# AgentCore

**Runtime-agnostic orchestration layer for AI coding agents.**

AgentCore is **not** Hermes, Kilo, OpenCode, Claude Code, or any other AI coding agent.
It is the orchestration layer that sits *above* them:

```
                    AgentCore
                       │
             ┌─────────┴─────────┐
             │   RuntimeAdapter  │
             └─────────┬─────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Hermes         Echo       Future
          │            │         runtimes
          ▼            ▼
       execution    execution
          │            │
          └──────┬─────┘
                 ▼
              EventBus
                 │
        ┌────────┼─────────┐
        ▼        ▼         ▼
      Tasks  Observations Memory
                           │
                           ▼
                       DB-Obsidian
```

AgentCore provides the task lifecycle, event bus, observations, memory harvesting,
and verification infrastructure. The runtime performs the actual agent execution.
Different runtimes can have different capabilities — the same AgentCore
infrastructure operates across all of them.

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

# Install AgentCore from GitHub (not yet on PyPI)
pip install "agentcore @ git+https://github.com/AngKool-Dev/agent-core.git"

# Verify
python -c "import agentcore; print(agentcore.__version__)"

# Run a task (requires a runtime adapter)
agent "Fix the launcher crash"

# Inspect results without a runtime
argus task list
```

> **Python 3.11+** is required. AgentCore has **no required dependencies.**
> Runtimes, memory backends, and tools are optional and loaded lazily.

### What's installed

| Command | Description |
|---|---|
| `agent` | Run an AI coding agent (requires a runtime adapter) |
| `argus` | Read-only observability CLI — works without any runtime |

---

## Run Your First AgentCore Task

AgentCore is designed to sit **above** an existing agent runtime. It provides
orchestration, lifecycle, events, observations, and memory — the runtime
performs the actual execution.

The general flow:

```
User / Application
       │
       ▼
  AgentCore task
       │
       ▼
  RuntimeRegistry
       │
       ▼
  RuntimeAdapter
       │
       ▼
  Agent execution
       │
       ├── events
       ├── output
       └── result
       │
       ▼
  AgentCore EventBus
       │
       ├── Task lifecycle
       ├── Observations
       └── Memory harvesting
       │
       ▼
  argus task show <task_id>
  argus task events <task_id>
  argus task memories <task_id>
```

### Case 1 — Existing AgentCore-compatible runtime

If the project already has an AgentCore runtime adapter (e.g. Hermes, Echo):

```bash
# List available adapters
agent --list-runtimes

# Run a task through the adapter
agent -r <runtime-name> "Your task here"

# Inspect results
argus task list
argus task show <task_id>
argus task events <task_id>
argus task memories <task_id>
```

AgentCore will:
1. Discover project context (language, files, structure)
2. Plan the task (investigate → implement → verify)
3. Route to the runtime for execution
4. Harvest memories with confidence scoring
5. Verify results with format/build/test checks
6. Persist everything for later inspection via `argus`

### Case 2 — Existing agent runtime, no AgentCore adapter

**Do NOT replace the existing agent runtime.**

Inspect its execution interface and determine whether a `RuntimeAdapter` can
integrate it. The architecture is:

```
Existing Agent
       │
       ▼
RuntimeAdapter
       │
       ▼
AgentCore
```

The runtime remains responsible for execution. AgentCore becomes responsible
for orchestration, lifecycle, events, observations, and memory.

See [`docs/runtime-adapters.md`](docs/runtime-adapters.md) for how to implement
a `RuntimeAdapter`.

### Case 3 — No existing runtime

AgentCore can still be used as the orchestration foundation, but an actual
runtime/agent implementation is required to perform LLM work.

AgentCore itself does **not** provide an LLM.

### Runtime selection

| Your situation | What to do |
|---|---|
| Using Hermes Desktop | Use `HermesRuntime` |
| Using an existing supported AgentCore runtime | Use that adapter |
| Using another agent/runtime | Implement or add a `RuntimeAdapter` |
| Building a new agent | Build the runtime around `RuntimeAdapter` |
| Need persistent memory | Configure DB-Obsidian |
| Need simple local testing | Use `InMemoryBackend` |

**Hermes is NOT required. DB-Obsidian is NOT required. AgentCore does NOT require a specific LLM. AgentCore does NOT replace the agent runtime.**

---

## Multi-Runtime Architecture

AgentCore is a **verified multi-runtime orchestration layer**. The same task
lifecycle, event system, observations, and memory pipeline operate across
different runtimes without any changes to AgentCore core logic.

This is not merely a planned extension — it has been integration-tested with
multiple runtimes.

### Verified runtimes

| Runtime | Tool Calls | External Tool Execution | Role |
|---|---:|---:|---|
| **Hermes** | No | No | Black-box runtime — executes tools internally |
| **Echo** | Yes | Yes | Tool-aware runtime — AgentCore executes tools |
| Future runtimes | varies | varies | Kilo, OpenCode, custom adapters |

The capability difference matters:

- **Hermes** (`-z` mode) is a black-box runtime. It internally executes tools
  and returns only the final synthesized text. AgentCore sees `tool_calls=[]`
  and skips the tool-execution state machine.
- **Echo** is a tool-aware runtime. It returns `ToolCall` objects in its
  response and expects AgentCore to execute them via `ToolManager`.

Both runtimes share the same AgentCore infrastructure: task lifecycle, event
bus, observation collection, memory harvesting, and CLI observability.

### Runtime routing

Tasks are explicitly routed to a runtime via the `-r` flag:

```bash
agent -r hermes "Fix the bug"     # Uses Hermes runtime (black-box)
agent -r echo "Echo this"         # Uses Echo runtime (tool-aware)
agent --list-runtimes             # Shows all available adapters
```

The runtime adapter is resolved at execution time from the `RuntimeRegistry`.
No AgentCore core code changes are needed to add a new runtime.

---

## Architecture

```
                USER
                 │
                 ▼
        ┌──────────────┐
        │   AgentCore   │   ← Task lifecycle, persistence, limits, events
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
       RuntimeAdapter    ← Hermes, Echo, Kilo, OpenCode
              │
              ▼
         Execution system
```

### Layer table

| Layer | Responsibility |
|---|---|
| **AgentCore** | Task lifecycle (state machine), persistence, resource limits, graceful shutdown |
| **Context** | Project context discovery (language type, file inventory, exclude patterns) |
| **Skills** | Skill discovery from filesystem, prompt-based routing |
| **Memory** | Optional memory storage (InMemoryBackend default, DB-Obsidian adapter optional) |
| **Planner** | Plan generation and replanning |
| **RuntimeAdapter** | Abstract interface to runtime execution (Hermes, Echo, Kilo, OpenCode) |
| **Verifier** | Post-completion verification (format, build, tests) with scope control |
| **Argus** | Read-only CLI for inspecting tasks, observations, and memory |

### What AgentCore does NOT do

AgentCore is infrastructure, not an agent. It does **not**:

- Generate code or provide a coding model
- Provide an LLM or model backend (delegated to the runtime adapter)
- Replace Hermes, Kilo, OpenCode, Claude Code, or any other agent
- Replace an agent's user interface
- Automatically integrate with every agent (an adapter is required per agent)

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

### Built-in runtimes

**Hermes Runtime** (reference integration):

```python
from agentcore import HermesRuntime

runtime = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
response = runtime.respond({"user_request": "Explain dependency injection"})
# RuntimeResponse(content="...", finish_reason=FinishReason.STOP)
```

**Echo Runtime** (reference implementation):

```python
from agentcore import EchoRuntime

runtime = EchoRuntime()
response = runtime.respond({"user_request": "Hello"})
# RuntimeResponse(content="Echo: Hello", finish_reason=FinishReason.STOP)
```

See [`docs/runtime-adapters.md`](docs/runtime-adapters.md) for the full adapter
contract and how to integrate Kilo, OpenCode, or your own runtime.

---

## Adding a New Runtime

A new runtime does not require rewriting AgentCore. The integration model is:

1. **Implement `RuntimeAdapter`** — subclass and implement `respond()` and
   `capabilities()`
2. **Declare capabilities** — advertise what the runtime supports via the
   standardized `RuntimeCapabilities` keys
3. **Implement execution** — translate AgentCore context into runtime-specific
   execution, return `RuntimeResponse`
4. **Implement cancellation/shutdown** — where supported, implement
   `RuntimeAdapter.cancel()`
5. **Register the runtime** — add a factory to `RuntimeRegistry`
6. **Add integration tests** — verify task lifecycle, observations, and memory
   harvesting work through the new runtime
7. **Verify** — run `pytest tests/ -q` and confirm no regressions

Echo exists partly as a minimal reference/example runtime proving the adapter
boundary. Hermes is the production integration.

See [`docs/runtime-adapters.md`](docs/runtime-adapters.md) for the complete guide.

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

### From GitHub (current method)

```bash
pip install "agentcore @ git+https://github.com/AngKool-Dev/agent-core.git"
```

> **Note:** `pip install agentcore` from PyPI currently installs a *different*
> package (an agentsea library). AgentCore is not yet published to PyPI under
> its own name. Always use the GitHub installation method above.

### From source

```bash
git clone https://github.com/AngKool-Dev/agent-core.git
cd agent-core
pip install -e ".[dev]"
```

---

## Python API

```python
from agentcore import Agent, AgentConfig, AgentCoreConfig, create_agent_core

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
max_runtime_seconds = 300      # Max total runtime per task
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
| Real runtime | Hermes | No — opt-in |

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

| If you want to... | Read |
|---|---|
| Understand the architecture | [`docs/architecture.md`](docs/architecture.md) |
| Implement a runtime adapter | [`docs/runtime-adapters.md`](docs/runtime-adapters.md) |
| Use the Argus CLI | [`docs/cli-reference.md`](docs/cli-reference.md) |
| Integrate Hermes Desktop | [`docs/hermes-integration.md`](docs/hermes-integration.md) |
| Understand memory & confidence | [`docs/memory.md`](docs/memory.md) |
| Integrate as an AI coding agent | [`AGENTCORE.md`](AGENTCORE.md) |

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

## Roadmap

| Phase | Focus | Status |
|---|---|---|
| 6A | Training dataset v016 | Complete |
| 6B | Release audit (lint, CI, packaging) | Complete |
| 6C | Release candidate hardening | Complete |
| 6D | Release documentation | Complete |
| 6E | GitHub release | Complete |
| Multi-runtime proof | Echo runtime + integration tests | Complete |
| 7 | Advanced memory consolidation (eviction, promotion) | Planned |
| 8 | Multi-runtime orchestration | Planned |

---

## License

MIT — see [LICENSE](LICENSE).
