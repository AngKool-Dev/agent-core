# Runtime Adapters

This is the canonical guide for developers implementing new AgentCore runtimes.
It documents the `RuntimeAdapter` interface, the registry, the execution flow,
and the boundaries between AgentCore and the runtime.

## 1. What RuntimeAdapter Is

`RuntimeAdapter` is the abstract interface between AgentCore and an agent runtime.
It defines how AgentCore sends a task context to the runtime and receives a
structured response back.

```python
from agentcore.runtimes.base import RuntimeAdapter, RuntimeResponse, FinishReason


class MyRuntime(RuntimeAdapter):
    def respond(self, context: dict[str, Any]) -> RuntimeResponse: ...
    def capabilities(self) -> dict[str, Any]: ...
    def cancel(self) -> None: ...

    @property
    def default_model(self) -> str | None:
        return None
```

## 2. Runtime Responsibilities

The runtime is responsible for:

- Receiving a structured `context` dict from AgentCore
- Translating that context into the runtime's native execution model
- Producing a `RuntimeResponse` with `content`, `tool_calls`, `finish_reason`,
  and optional `metadata`
- Handling cancellation via `cancel()`
- Reporting capabilities honestly via `capabilities()`

The runtime is **not** responsible for:
- Task lifecycle management (AgentCore owns this)
- Event bus or observation collection (AgentCore owns this)
- Memory harvesting (AgentCore owns this)
- Tool execution (AgentCore's `ToolManager` owns this, unless the runtime
  declares `external_tool_execution=False`)

## 3. AgentCore Responsibilities

AgentCore is responsible for:

- Building the execution context from task state, project context, memory,
  skills, and instructions
- Managing the task lifecycle state machine
- Operating the `EventBus` for event propagation
- Collecting observations via `ObservationCollector`
- Harvesting memories via `MemoryHarvester`
- Executing tool calls via `ToolManager` (when `external_tool_execution=True`)
- Persisting task state via `TaskPersistenceManager`
- Verifying results via `Verifier`
- CLI observability via `argus`

## 4. RuntimeCapabilities

Runtimes declare capabilities via `capabilities()`:

| Key | Type | Meaning |
|---|---|---|
| `text_generation` | `bool` | Runtime produces text responses |
| `tool_calls` | `bool` | Runtime exposes structured `ToolCall` objects to AgentCore |
| `external_tool_execution` | `bool` | AgentCore executes those tools via `ToolManager` |
| `streaming` | `bool` | Runtime supports streaming responses |
| `cancellation` | `bool` | Runtime supports cancellation |

Example:

```python
{
    "text_generation": True,
    "tool_calls": True,
    "external_tool_execution": True,
    "streaming": False,
    "cancellation": False,
}
```

Additional metadata keys are allowed: `adapter`, `model`, `provider`, `timeout`.

## 5. RuntimeRegistry

`RuntimeRegistry` stores runtime factories by name and resolves them at
execution time:

```python
from agentcore.runtimes import get_default_registry

reg = get_default_registry()

# List all registered runtimes
print(reg.list_runtimes())

# Query capabilities without instantiating
caps = reg.get_capabilities("echo")

# Create a runtime by name
runtime = reg.create("hermes", model="claude-sonnet-4")

# Register a new runtime
reg.register(
    "my-runtime",
    lambda **kw: MyRuntime(),
    info={
        "description": "My custom runtime",
        "capabilities": {...},
    },
)
```

Built-in runtimes are registered in `_register_builtin_runtimes()`. Third-party
runtimes can register themselves at any time.

## 6. Execution Flow

```
Agent
  ↓
TaskPersistenceManager (load/save task state)
  ↓
ContextBuilder (project context + memory + skills + instructions)
  ↓
RuntimeRegistry.resolve(runtime_name)
  ↓
RuntimeAdapter.respond(context)
  ↓
RuntimeResponse (content, tool_calls, finish_reason, metadata)
  ↓
ToolManager.execute(tool_calls)       [if external_tool_execution=True]
  ↓
ObservationCollector (records observations)
  ↓
MemoryHarvester (extracts memory candidates)
  ↓
MemoryBackend (stores memories)
  ↓
Verifier (format/build/test checks)
  ↓
TaskPersistenceManager (save final state)
```

## 7. Event Emission

Events flow from the runtime → AgentCore's `EventBus` → `ObservationCollector`.

The runtime does not write directly to the observation store or memory backend.
AgentCore's event system provides the decoupling. Events include:

- `task.started` — task execution begins
- `task.state_changed` — task transitions to a new state
- `tool_call.started` — a tool call begins
- `tool_call.completed` — a tool call finishes
- `runtime_error` — the runtime produced an error
- `task.completed` — task finished successfully
- `task.failed` — task finished with failure
- `task.cancelled` — task was cancelled

## 8. Observation Collection

`ObservationCollector` subscribes to `EventBus` events and creates `Observation`
objects with stable correlation IDs:

- `observation.id` — deterministic ID
- `session_id` — runtime session UUID
- `task_id` — task identifier
- `turn_id` — per-iteration identifier

Observations are stored in `ObservationStore` (in-memory or DB-Obsidian).

## 9. Memory Harvesting

`MemoryHarvester` subscribes to observations and extracts `MemoryCandidate`
objects. The runtime does not participate in memory harvesting — it only
produces observations. AgentCore's harvesting layer operates identically
regardless of which runtime produced the observations.

Memory candidates are identified by a deterministic ID:
`SHA-256(content + project_path + memory_type)`.

## 10. Cancellation

Cancellation flows through `RuntimeAdapter.cancel()`. AgentCore calls `cancel()`
when:

- The user requests shutdown (SIGINT)
- The runtime exceeds its configured timeout
- The task exceeds its resource limits

The runtime is responsible for terminating its own execution (subprocess,
thread, session, etc.).

## 11. Shutdown

When a task completes (success, failure, or cancellation), AgentCore:

1. Emits a final `task.completed` or `task.failed` event
2. Runs the verifier (format/build/test checks)
3. Harvests memories from remaining observations
4. Persists final task state
5. Cleans up runtime resources

The runtime should not hold open resources after `respond()` returns.

## 12. Error Handling

Runtime errors are reported via `RuntimeResponse` with `finish_reason=ERROR`
and an `error` key in `metadata`. AgentCore catches errors in `respond()`,
transitions the task to `FAILED`, and emits a `runtime_error` event.

If the runtime raises an exception (rather than returning an error response),
AgentCore catches it, transitions the task to `FAILED`, and preserves partial
observations.

## 13. Testing Requirements

Every runtime adapter must have integration tests that verify:

- The runtime is registered in `RuntimeRegistry`
- The runtime conforms to `RuntimeAdapter`
- Task lifecycle works through the runtime (task starts, runs, completes)
- Observations are collected from the runtime's events
- Memory harvesting works with observations produced by the runtime
- The runtime's declared capabilities match its actual behavior

See `tests/test_multi_runtime.py` for the Echo runtime integration tests.

## 14. Echo: Reference Implementation

Echo is a minimal runtime adapter that demonstrates the adapter boundary:

```python
from agentcore import EchoRuntime

runtime = EchoRuntime()
response = runtime.respond({"user_request": "Hello"})
# RuntimeResponse(content="Echo: Hello", finish_reason=FinishReason.STOP)
```

Echo is:
- **Tool-aware** (`tool_calls=True`, `external_tool_execution=True`)
- **Deterministic** — always returns the same response for the same input
- **Minimal** — no external dependencies, no subprocess, no network

Echo exists partly as a reference/example runtime proving the adapter boundary.
It is not intended for production use with real language models.

## 15. Hermes: Production Integration

Hermes is the production runtime integration:

```python
from agentcore import HermesRuntime

runtime = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
```

Hermes is:
- **Black-box** (`tool_calls=False`, `external_tool_execution=False`)
- **Subprocess-based** — drives the `hermes -z` CLI
- **Production-ready** — verified against real Hermes Desktop sessions

See [`docs/hermes-integration.md`](docs/hermes-integration.md) for the full
Hermes Desktop integration details.
