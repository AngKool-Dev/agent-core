# Argus CLI Reference

Argus is the read-only observability CLI for AgentCore. It inspects persisted
tasks, observations, and memory. Argus does not require a runtime (Hermes, Kilo,
OpenCode) to be installed. It connects to the same data directory that a running
AgentCore session writes to.

## Connecting to Data

Argus reads from `user_data_dir/agentcore`:

| Component | Source | Fallback |
|---|---|---|
| Task registry | Filesystem (`tasks/` directory) | Empty registry |
| Observations | `DBObsidianObservationStore` | `InMemoryObservationStore` |
| Memory | `DBObsidianBackend` | `InMemoryBackend` |

If `db-obsidian` is not installed, all backends fall back to in-memory. This means
Argus will show no tasks or memories until an AgentCore session with db-obsidian
writes them.

## Commands

### `argus task list`

List registered tasks in the task registry.

```
argus task list [OPTIONS]
```

**Options:**

| Option | Description |
|---|---|
| `--state TEXT` | Filter by task state (e.g. `running`, `completed`, `failed`) |
| `--source TEXT` | Filter by task source (e.g. `agent`, `hermes`) |
| `--runtime TEXT` | Filter by runtime adapter name |
| `--limit INTEGER` | Maximum tasks to display |
| `--json` | Output as JSON |

**Return codes:**

- `0` — success (even if no tasks match)
- `1` — query service initialization failure

**Example:**

```bash
argus task list --state running
```

---

### `argus task show`

Show details for a single task.

```
argus task show <task_id> [OPTIONS]
```

**Positional arguments:**

| Argument | Description |
|---|---|
| `task_id` | The task ID (e.g. `hermes-abc123-task456`) |

**Options:**

| Option | Description |
|---|---|
| `--json` | Output as JSON |

**Return codes:**

- `0` — success
- `1` — task not found, or internal CLI error

**Example:**

```bash
argus task show hermes-abc123-task456
argus task show hermes-abc123-task456 --json
```

---

### `argus task events`

Show observations (events, tool calls, results) recorded for a task.

```
argus task events <task_id> [OPTIONS]
```

**Positional arguments:**

| Argument | Description |
|---|---|
| `task_id` | The task ID |

**Options:**

| Option | Description |
|---|---|
| `--limit INTEGER` | Maximum observations to show (default: 1000) |
| `--full` | Show full payload (truncated by default) |
| `--json` | Output as JSON array |

**Return codes:**

- `0` — success (even if no observations exist)
- `1` — task not found, or query service failure

**Example:**

```bash
argus task events hermes-abc123-task456 --limit 50
```

---

### `argus task memories`

Show memories harvested for a task.

```
argus task memories <task_id> [OPTIONS]
```

**Positional arguments:**

| Argument | Description |
|---|---|
| `task_id` | The task ID |

**Options:**

| Option | Description |
|---|---|
| `--min-confidence TEXT` | Filter by confidence (float in [0,1] or enum name) |
| `--type TEXT` | Filter by memory type (e.g. `task`, `fact`, `decision`, `error`, `learning`) |
| `--limit INTEGER` | Maximum memories to show (default: 50) |
| `--json` | Output as JSON array |

**Confidence filters:** Use `VERIFIED` (1.0), `CLAIMED` (0.7),
`INFERRED` (0.5), `UNKNOWN` (0.3), or a raw float like `0.6`.

**Return codes:**

- `0` — success (even if no memories exist)
- `1` — task not found, or query service failure

**Example:**

```bash
argus task memories hermes-abc123-task456 --min-confidence CLAIMED
```

---

### `argus memory search`

Search across all stored memories.

```
argus memory search <query> [OPTIONS]
```

**Positional arguments:**

| Argument | Description |
|---|---|
| `query` | Search query string |

**Options:**

| Option | Description |
|---|---|
| `--limit INTEGER` | Maximum results (default: 20) |
| `--type TEXT` | Filter by memory type |
| `--min-confidence TEXT` | Filter by confidence (float or enum name) |
| `--json` | Output as JSON array |

**Return codes:**

- `0` — success (even if no results match)
- `1` — search failed or query service failure

**Example:**

```bash
argus memory search "dependency injection" --limit 10 --json
```

---

### `argus memory show`

Show details for a single memory record.

```
argus memory show <memory_id> [OPTIONS]
```

**Positional arguments:**

| Argument | Description |
|---|---|
| `memory_id` | The memory record ID (e.g. `mem-a1b2c3d4e5f6`) |

**Options:**

| Option | Description |
|---|---|
| `--json` | Output as JSON |

**Return codes:**

- `0` — success
- `1` — memory not found, or query service failure

**Example:**

```bash
argus memory show mem-a1b2c3d4e5f6
```

---

### `argus memory confidence`

Show confidence diagnostic for a memory record, including the confidence
reasoning and source observations.

```
argus memory confidence <memory_id> [OPTIONS]
```

**Positional arguments:**

| Argument | Description |
|---|---|
| `memory_id` | The memory record ID |

**Options:**

| Option | Description |
|---|---|
| `--json` | Output as JSON |

**Return codes:**

- `0` — success
- `1` — memory not found, or query service failure

**Example:**

```bash
argus memory confidence mem-a1b2c3d4e5f6 --json
```
