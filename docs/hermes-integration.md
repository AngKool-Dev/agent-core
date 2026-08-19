# Hermes Desktop Integration

AgentCore integrates with [Hermes Desktop](https://github.com/hermes-desktop/hermes-desktop)
as the default execution runtime. This integration is:

- **Lazy**: Hermes is not imported or required at AgentCore install time
- **Optional**: AgentCore works without Hermes; Hermes is only needed to execute tasks
- **One-way**: AgentCore observes and controls through explicit Hermes interfaces

Hermes remains the **execution authority**. Argus observes and controls through
explicit Hermes interfaces — it does not replace Hermes.

## Components

### HermesEventBridge

`HermesEventBridge` connects to a Hermes Desktop session via a Unix domain socket
or named pipe and listens for lifecycle events:

```
Hermes Desktop Session
    │
    ├── session.start
    ├── session.end
    ├── task.created
    ├── task.updated
    ├── turn.start
    ├── turn.end
    ├── observation.received
    ├── task.cancelled
    └── session.disconnected
    │
    ▼
HermesEventBridge
    │
    ├── EventBus (local)
    └── ObservationStore
```

The bridge is the **only** component that communicates directly with Hermes.
All other AgentCore components consume events through the local EventBus.

### DesktopTaskCoordinator

`DesktopTaskCoordinator` translates between AgentCore's task model and Hermes'
task model:

```
AgentCore Task                  ⟷              Hermes Task
──────────────────────                        ──────────────────────
task_id: str                  ⟷              session_id + local_task_id
user_request: str             ⟷              prompt
project_path: str             ⟷              projectPath
plan: PlanStep[]              ⟷              (internal Hermes context)
state: TaskState              ⟷              status
metadata: dict                ⟷              (Hermes turn metadata)
```

### HermesControlBridge

`HermesControlBridge` provides outbound control signals:

- `submit_task()` — create a new Hermes task
- `cancel_task()` — request cancellation of an in-flight task
- `query_status()` — check task status
- `get_session_info()` — retrieve session metadata

## Identity Model

Each execution is tracked with provenance metadata:

| Field | Source | Description |
|---|---|---|
| `session_id` | Hermes session UUID | Unique session identifier; used for deduplication |
| `task_id` | Hermes task ID | Local task identifier within a session |
| `turn_id` | Hermes turn UUID | Per-iteration identifier |
| `session_key` | Hermes session key | Cross-reference key for Hermes Desktop UI |

### Argus Task ID Format

Argus task IDs follow the pattern:

```
hermes-{session_id}-{task_id}
```

Example: `hermes-abc123def456-789`

This ensures global uniqueness across sessions and runtimes.

### One Session, Multiple Tasks

One Hermes session can create multiple Argus tasks when:

- A single session request spawns sub-tasks or parallel investigations
- The agent creates multiple top-level tasks within one session
- A task is split into investigation and implementation phases

Each Argus task is an independent unit of work with its own state lifecycle,
even if they share the same Hermes session.

## Task Registration

When AgentCore starts an agent task:

1. `DesktopTaskCoordinator` registers a new `TaskRecord` in `TaskRegistry`
2. The Hermes session ID is stored in `TaskRecord.metadata["hermes_session_id"]`
3. The Hermes task ID is stored in `TaskRecord.metadata["hermes_task_id"]`
4. The Hermes turn ID is stored in `TaskRecord.metadata["hermes_turn_id"]`

## Lifecycle Events

| Hermes Event | AgentCore Action |
|---|---|
| `session.start` | Initialize EventBus, ObservationStore |
| `task.created` | Register TaskRecord in TaskRegistry |
| `turn.start` | Mark task as `RUNNING` |
| `observation.received` | Append to ObservationStore |
| `turn.end` | Check for completion or replan |
| `task.cancelled` | Mark task as `CANCELLED`, emit shutdown |
| `session.end` | Clean up resources, final persistence |

## Observation Collection

All observations from a Hermes session are collected by `ObservationCollector`
and stored in `ObservationStore`. These observations serve as:

- Input to `MemoryHarvester` for memory extraction
- Audit trail for task debugging
- Input to `Verifier` for verification context

## Cancellation Flow

```
User                Argus                AgentCore             Hermes
 │                   │                   │                   │
 │   kill -INT       │                   │                   │
 │                  ─►                   │                   │
 │                  send SIGINT to       │                   │
 │                  Hermes process       │                   │
 │                   │                   │                   │
 │                   │                  ─►                   │
 │                   │                   send cancellation  │
 │                   │                   to event bridge    │
 │                   │                   │                  ─►
 │                   │                   │  cancel task     │
 │                   │                   │                  ◄─
 │                   │                   │                  │
 │                   │                   │  mark CANCELLED  │
 │                   │                   │                  │
 │                   │                  ◄─                   │
 │                   │   propagate status                   │
 │                  ◄─                                     │
 │   return exit code                                     │
```

Cancellation is best-effort. AgentCore sends the cancellation signal through
the Hermes control bridge, but the actual termination is performed by Hermes.

## Failure Isolation

If Hermes Desktop crashes or disconnects:

1. `HermesEventBridge` detects the socket disconnect
2. All pending tasks are marked as `FAILED` with error `runtime_disconnected`
3. Partial observations are preserved in `ObservationStore`
4. `MemoryHarvester` runs on available observations before shutdown
5. Task state is persisted to filesystem

## Prerequisites

To use Hermes integration:

1. Install [Hermes Desktop](https://github.com/hermes-desktop/hermes-desktop)
2. Start a Hermes session
3. Configure the session socket path in `agentcore.toml`:

```toml
[agent]
runtime = "hermes"
session_socket = "/tmp/hermes-session.sock"
```

The socket path varies by platform. AgentCore auto-detects the default path on
macOS and Windows.
