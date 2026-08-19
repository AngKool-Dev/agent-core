# AgentCore

Universal AI coding-agent framework with pluggable runtime adapters.

**v0.1.0 — First public release**

## The Principle

**THE AGENT BRAIN IS SEPARATE FROM THE AGENT RUNTIME.**

AgentCore provides the orchestration layer: task state management, skill routing,
project context, memory, planning, verification, and tool execution.

Runtimes are interchangeable plug-ins. Hermes is the first runtime. Kilo and
OpenCode can be added later without changing AgentCore's core logic.

## Quick Start

```bash
# Create a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate

# Linux/macOS:
source .venv/bin/activate

# Install AgentCore (no external dependencies required)
pip install agentcore

# Or install from source with dev tools:
git clone https://github.com/agentcore/agent-core.git
cd agent-core
pip install -e ".[dev]"
```

Run a task:

```bash
# Requires Hermes runtime (optional - see Runtime Architecture)
agent "Fix the launcher crash"

# Use a specific project
agent -p /path/to/project "Why does launch fail?"

# Use a specific runtime
agent -r hermes -m claude-sonnet-4 "Implement X"

# List available runtimes
agent --list-runtimes
```

## Argus CLI

The `argus` command provides read-only inspection of tasks, observations, and memory.
It works without any runtime installed and does not require db-obsidian.

```bash
# List tasks (filters: --state, --source, --runtime, --json)
argus task list

# Show task details
argus task show <task_id>          # human-readable
argus task show <task_id> --json   # JSON output

# Show observations for a task
argus task events <task_id> [--limit N] [--full] [--json]

# Show memories for a task
argus task memories <task_id> [--min-confidence VERIFIED|0.7] [--type TYPE] [--limit N] [--json]

# Search memories
argus memory search <query> [--limit N] [--type TYPE] [--min-confidence F] [--json]

# Show a specific memory
argus memory show <memory_id> [--json]

# Show confidence diagnostic for a memory
argus memory confidence <memory_id> [--json]
```

See [Argus CLI Reference](docs/cli-reference.md) for full documentation.

## Architecture

```
                    USER
                     │
                     ▼
            ┌─────────────┐
            │  AgentCore  │   ← Task lifecycle, persistence, limits
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
            Runtime Adapter    ← Hermes, Kilo, OpenCode
                   │
                   ▼
               Hermes CLI
```

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

### Runtime Architecture

Runtimes are pluggable adapters implementing `RuntimeAdapter`. The default runtime
is Hermes (via `hermes -z`). AgentCore requires no specific runtime to be installed —
runtimes are loaded lazily and only when needed.

```
AgentCore                        Runtime Adapter
   │                                    │
   │  RuntimeCapabilities:              │  capabilities() returns:
   │  text_generation                    │  text_generation: bool
   │  tool_calls                         │  tool_calls: bool
   │  external_tool_execution            │  external_tool_execution: bool
   │  streaming                          │  streaming: bool
   │  cancellation                       │  cancellation: bool
   │                                    │
   └──► respond(context) ──────────────►│
   ├─── tool_calls (if enabled) ─◄──────┤
   └──◄── content + finish_reason ───────┘
```

**Tool execution ownership** is determined by capability flags:

| Runtime type | `tool_calls` | `external_tool_execution` | Behavior |
|---|---|---|---|
| Tool-aware | `true` | `true` | AgentCore executes tools, observes results |
| Black-box | `false` | `false` | Runtime handles tools internally |

Hermes v0.20+ in `-z` mode is a black-box runtime.

### Argus Architecture

Argus is the observability layer — a read-only CLI that inspects persisted state.

```
argus CLI
    │
    ▼
QueryService          ← assembles backends from config
    │
    ├── TaskRegistry     (from persistence)
    ├── ObservationStore  (DBObsidianObservationStore or InMemory)
    └── MemoryBackend     (DBObsidianBackend or InMemory)
```

Argus connects to the same DB-Obsidian databases that a running AgentCore session
writes to. If db-obsidian is not installed, Argus falls back to in-memory backends
(will report no tasks or memories until AgentCore writes them).

### Hermes Desktop Integration

AgentCore integrates with [Hermes Desktop](https://github.com/hermes-desktop/hermes-desktop)
as the default execution runtime. This integration is:

- **Lazy**: Hermes is not imported or required at AgentCore install time
- **Optional**: AgentCore works without Hermes; Hermes is only needed to execute tasks
- **One-way**: AgentCore observes and controls through explicit Hermes interfaces

The identity model maps each execution to provenance metadata:

| Field | Source | Used for |
|---|---|---|
| `session_id` | Hermes session UUID | Deduplication, task grouping |
| `task_id` | Hermes turn task ID | Argus task ID prefix (`hermes-`) |
| `turn_id` | Hermes turn UUID | Per-turn observation tracking |
| `session_key` | Hermes session key | Cross-reference with Hermes UI |

One Hermes session can produce multiple Argus tasks when a single session request
spawns sub-tasks or parallel investigations — each gets a distinct task ID.

### Memory Architecture

```
Agent → ObservationCollector → ObservationStore
                    │
                    ▼
            MemoryHarvester
                    │
                    ▼
            MemoryCandidate  ← deterministic ID (SHA-256 of content+context)
                    │
                    ▼
            MemoryBackend
                    │
                    ├── DBObsidianBackend   (persistent, requires db-obsidian)
                    └── InMemoryBackend      (ephemeral, default)
```

Confident memories are stored as `MemoryRecord` with a confidence level:

| Level | Score | Meaning |
|---|---|---|
| `UNKNOWN` | 0.3 | Inferred from observation; no explicit claim |
| `INFERRED` | 0.5 | Derived from task execution patterns |
| `CLAIMED` | 0.7 | Explicitly stated by the model in an observation |
| `VERIFIED` | 1.0 | Matches a verified tool outcome |

Confidence classification is deterministic in v0.1.0.

## Configuration

AgentCore loads configuration from TOML files in priority order:

1. Explicit config: `agent --config path/to/agentcore.toml`
2. Project-local: `./agentcore.toml` or `./config/agentcore.toml`
3. User-level: `{user_config_dir}/agentcore/agentcore.toml`
4. Built-in defaults

| Setting | Default | Description |
|---|---|---|
| `default_runtime` | `"hermes"` | Runtime adapter name |
| `model` | `null` | Override model (e.g. `"claude-sonnet-4"`) |
| `memory_backend` | `"in_memory"` | `"in_memory"` or `"db_obsidian"` |
| `memory_db_path` | `""` | Explicit DB path (empty = auto-detect) |
| `harvesting_enabled` | `true` | Enable memory harvesting during tasks |
| `max_iterations` | `10` | Max agent loop iterations per task |
| `max_tool_calls` | `50` | Max tool calls per task |
| `timeout` | `300` | Per-request timeout (seconds) |
| `run_format_check` | `true` | Run format check on verification |
| `run_build_check` | `true` | Run build check on verification |
| `run_tests` | `true` | Run test suite on verification |
| `verification_scope` | `"project"` | `"project"` or `"changed-files"` |
| `max_context_files` | `50` | Max files for project context |
| `exclude_patterns` | see config | Glob patterns to exclude from context |

### Memory Backend

AgentCore supports two memory backends:

| Backend | Persistent | Dependencies |
|---|---|---|
| `in_memory` (default) | No | None — built in |
| `db_obsidian` | Yes (SQLite + Obsidian vault) | `pip install agentcore[db-obsidian]` |

`db-obsidian` is an **optional**, separate package available from
[AngKool-Dev/db-obsidian on GitHub](https://github.com/AngKool-Dev/db-obsidian).
It is not currently published to PyPI. If it is not installed, AgentCore
automatically falls back to `InMemoryBackend` at startup. To enable persistent
memory:

```bash
pip install git+https://github.com/AngKool-Dev/db-obsidian
```

Or via the extras syntax (requires PyPI access to `agentcore`):

```bash
pip install agentcore[db-obsidian]
```

Then configure:

```toml
[memory]
backend = "db_obsidian"
db_path = "~/.agentcore/memory.db"
```

## Python API

```python
from agentcore import Agent, AgentConfig, AgentCoreConfig, create_agent, create_agent_core

# Create AgentCore facade (task lifecycle, persistence)
core = create_agent_core(config=AgentCoreConfig(default_runtime="hermes"))

# Create an agent with a runtime and memory backend
from agentcore import HermesRuntime, MemoryManager, InMemoryBackend

runtime = HermesRuntime(model="claude-sonnet-4")
memory = MemoryManager(InMemoryBackend())
config = AgentConfig(max_iterations=10, enable_verification=True)

agent = Agent(runtime=runtime, memory=memory, config=config)
result = agent.execute("Fix the failing tests")
```

## Extending AgentCore

### Custom Runtime

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
```

Register it:

```python
from agentcore.runtimes import get_default_registry

registry = get_default_registry()
registry.register("my-runtime", lambda **kw: MyRuntime())
```

### Custom Tool

```python
from agentcore.tools import ToolManager, ToolResult


def my_tool(args: dict, work_dir, start: float) -> ToolResult:
    return ToolResult(success=True, tool="my_tool", output="done")


manager = ToolManager(project_path=".")
manager.register_tool("my_tool", my_tool)
```

## Examples

- `examples/basic_agent.py` — Minimal agent with an echo runtime
- `examples/custom_runtime.py` — Implementing a RuntimeAdapter
- `examples/custom_tool.py` — Registering a custom tool

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run default test suite (fast, deterministic)
pytest tests/ -q

# Run real-runtime tests (requires Hermes installed)
AGENTCORE_REAL_RUNTIME=1 pytest -m real_runtime -q
```

### Test Tiers

| Tier | Runtime | Default? |
|---|---|---|
| Unit | Mocked | Yes |
| Integration | Deterministic/mock | Yes |
| Real runtime | Hermes/Kilo/OpenCode | No |

The default `pytest -q` suite runs only unit and deterministic integration tests.
Real-runtime tests are explicitly opt-in via the `AGENTCORE_REAL_RUNTIME`
environment variable and the `real_runtime` marker.

### Validation Commands

```bash
# Full release gate
ruff check .
ruff format --check .
pytest tests/ -q
git diff --check
python -m build
```

## Documentation

- `docs/architecture.md` — System architecture and design
- `docs/cli-reference.md` — Argus CLI command reference
- `docs/runtime-adapters.md` — Runtime adapter interface and capability contract
- `docs/hermes-integration.md` — Hermes Desktop integration and identity model
- `docs/memory.md` — Memory harvesting, confidence, and backends

## Current Limitations

- v0.1.0 is a **framework release**, not a turnkey product. Integration with
  Hermes Desktop requires a running Hermes Desktop session.
- `db-obsidian` is not auto-installed or published to PyPI. Users must install it
  from GitHub for persistent memory:
  `pip install git+https://github.com/AngKool-Dev/db-obsidian`
  or `pip install agentcore[db-obsidian]` (when available on PyPI).
- Memory harvesting is deterministic but minimal. Advanced memory
  consolidation (eviction, promotion, clustering) is planned for future releases.
- The verifier runs format/build/test checks but does not auto-apply fixes.
- Real-runtime tests require Hermes Desktop to be installed on the host system.

## Roadmap

| Phase | Focus | Status |
|---|---|---|
| 6A | Training dataset v016 | Complete |
| 6B | Release audit (lint, CI, packaging) | Complete |
| 6C | Release candidate hardening | Complete |
| 6D | Release documentation (this phase) | Complete |
| 6E | GitHub release | Pending |
| 7 | Advanced memory consolidation | Planned |
| 8 | Multi-runtime orchestration | Planned |

## License

MIT — see [LICENSE](LICENSE).
