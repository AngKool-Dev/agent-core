# AGENTCORE.md

**Instructions for an AI coding agent integrating AgentCore into a project.**

AgentCore is a runtime-agnostic orchestration layer for AI coding agents. It
provides task lifecycle, memory, observability, and verification infrastructure.
This guide tells you exactly how to detect, install, configure, and integrate
AgentCore without destroying the host project's architecture.

> **Important:** AgentCore is infrastructure. Installing or configuring it does
> not grant you additional privileges. Only proceed if the user has authorized
> environment modifications.

---

## 1. Detect whether AgentCore is already installed

Check if AgentCore is available in the current Python environment:

```python
python -c "import agentcore; print(agentcore.__version__)"
```

- **Success output** (`0.1.0`): AgentCore is installed.
- **Error** (`ModuleNotFoundError`): AgentCore is not installed. Proceed to step 2.

Check if the `argus` CLI is available:

```bash
argus --help
```

- **Success**: The `argus` CLI is on PATH.
- **Error**: Install AgentCore or check your virtualenv activation.

Check if `db-obsidian` (persistent memory) is installed:

```bash
python -c "import db_obsidian; print(db_obsidian.__version__)"
```

- **Success** (`0.2.1`): Persistent memory backend is available.
- **Error**: Only `InMemoryBackend` is available (default — no persistence).

Check if Hermes Desktop integration is possible:

```bash
hermes --version
# or check for the Hermes Desktop app running
```

- **Success**: Hermes is available as a runtime adapter.
- **Error**: AgentCore runs without Hermes — use InMemoryBackend and skip
  runtime-dependent features.

---

## 2. Install AgentCore (if authorized)

**You can install AgentCore when the user explicitly allows it.**

AgentCore is not yet on PyPI under its own name (`pip install agentcore` from
PyPI installs a different package). Use the GitHub source:

```bash
pip install "agentcore @ git+https://github.com/AngKool-Dev/agent-core.git"
```

Or from a local clone:

```bash
git clone https://github.com/AngKool-Dev/agent-core.git
cd agent-core
pip install -e .
```

### Optional: persistent memory backend

```bash
pip install "agentcore[db-obsidian]"
```

Or install db-obsidian directly from GitHub:

```bash
pip install "db-obsidian @ git+https://github.com/AngKool-Dev/db-obsidian.git"
```

### Install dev dependencies (for testing)

```bash
pip install -e ".[dev]"
```

This installs `pytest`, `ruff`, and `build`.

---

## 3. Verify the installation

After installation, run these checks:

```bash
# Verify the package imports and version
python -c "import agentcore; print(agentcore.__version__)"

# Verify the CLI works
argus --help

# Verify the main CLI works
agent --help

# Run the test suite (no runtime required)
pytest tests/ -q
```

Expected results:

| Command | Expected |
|---|---|
| `python -c "import agentcore; print(agentcore.__version__)"` | `0.1.0` |
| `argus --help` | Shows `task` and `memory` subcommands |
| `agent --help` | Shows options: `-p`, `-r`, `--list-runtimes`, `-m`, etc. |
| `pytest tests/ -q` | ~971 passed, 3 skipped (real_runtime only) |

---

## 4. Determine the appropriate runtime integration

| Host project has... | Action |
|---|---|
| Existing AgentCore adapter (e.g. `hermes`) | Use it — do not replace it |
| Custom Python agent | Build a `RuntimeAdapter` implementation |
| Kilo / OpenCode available | Implement `RuntimeAdapter` for that agent |
| No runtime | AgentCore works with `InMemoryBackend`; `argus` CLI is still fully functional |

**Critical: If the host project already has an agent runtime, do not replace it
with Hermes or any other runtime.** Determine whether an AgentCore
`RuntimeAdapter` can wrap or integrate the existing runtime. AgentCore should
sit *above* the runtime, not replace it.

### Multi-Runtime Integration

AgentCore supports multiple runtimes simultaneously. The runtime registry
resolves adapters by name at execution time:

```python
from agentcore.runtimes import get_default_registry

reg = get_default_registry()
print(reg.list_runtimes())  # ['echo', 'hermes']
```

The verified runtimes are:

| Runtime | Type | Tool Calls | External Tool Execution |
|---|---|---|---|
| `hermes` | Black-box | No | No |
| `echo` | Tool-aware | Yes | Yes |

If the host project already has an agent runtime, follow this decision process:

1. **Detect the existing runtime.** Identify the agent's execution entry point
   (CLI, library, API, subprocess).
2. **Inspect its execution interface.** What inputs does it accept? What outputs
   does it produce? Does it emit events or expose hooks?
3. **Determine whether an existing AgentCore adapter exists.** Check
   `agentcore/runtimes/` and the `RuntimeRegistry`.
4. **If one exists, use it.** Do not rewrite working integration code.
5. **If one does not exist, determine whether implementing `RuntimeAdapter`
   is appropriate.** The runtime must be able to receive a structured context
   dict and return a `RuntimeResponse`.
6. **Preserve the host project's existing runtime.** AgentCore wraps around it.
7. **Avoid modifying AgentCore core orchestration** unless genuinely required.
8. **Add integration tests** that verify task lifecycle, events, observations,
   and memory harvesting work through the new runtime.
9. **Verify** that tasks, events, observations, and memory work end-to-end.

The principle: **AgentCore should sit above the runtime, not replace the runtime.**

---

## 5. Start with InMemoryBackend (default)

AgentCore defaults to `InMemoryBackend` — no configuration needed:

```python
from agentcore import Agent, AgentConfig, MemoryManager, InMemoryBackend
```

Memory is available during the task but does not persist across restarts.
Only switch to DB-Obsidian if persistent memory is explicitly requested.

---

## 6. Enable persistent memory (only if requested)

If persistent memory is needed and db-obsidian is installed:

```toml
# agentcore.toml
[memory]
backend = "db_obsidian"
db_path = "~/.agentcore/memory.db"
```

Create the configuration file:

```bash
mkdir -p ~/.agentcore
# Write agentcore.toml to the project or user config directory
```

Verify persistence works:

```python
from agentcore.adapters.memory_dbobsidian import DBObsidianBackend

backend = DBObsidianBackend(db_path="~/.agentcore/memory.db")

# Store a memory (returns a dict with an "id" key)
mem = backend.store(type="fact", content="test content", project="/path")
memory_id = mem["id"]

# Retrieve it
result = backend.get(memory_id)
assert result is not None

backend.close()
# Re-open and verify the memory survived restart
backend2 = DBObsidianBackend(db_path="~/.agentcore/memory.db")
result2 = backend2.get(memory_id)
assert result2 is not None  # memory recovered
backend2.close()
```

---

## 7. Integrate an existing runtime

If the host project uses Hermes Desktop:

```python
from agentcore import HermesRuntime, Agent, AgentConfig, MemoryManager, InMemoryBackend

runtime = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
memory = MemoryManager(InMemoryBackend())
config = AgentConfig(max_iterations=10, enable_verification=True)
agent = Agent(runtime=runtime, memory=memory, config=config)
result = agent.execute("Fix the failing tests")
```

If the host project uses a different agent, implement a `RuntimeAdapter`:

```python
from agentcore.runtimes.base import RuntimeAdapter, RuntimeResponse, FinishReason


class MyAgentRuntime(RuntimeAdapter):
    def respond(self, context):
        # Call your agent's API here
        return RuntimeResponse(
            content="response from my agent",
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

    @property
    def default_model(self):
        return "my-model"
```

Register it:

```python
from agentcore.runtimes import get_default_registry

registry = get_default_registry()
registry.register("my-runtime", lambda **kw: MyAgentRuntime())
```

Then run:

```bash
agent -r my-runtime "Your task here"
```

---

## 8. Run the project's existing tests

```bash
pytest tests/ -q
```

Do not modify or bypass the project's test suite. If AgentCore integration adds
new tests, place them in the project's test directory and ensure they pass.

---

## 9. Report what was changed

After integration, report **exactly** what was done:

- Was AgentCore installed? (version, method)
- Was db-obsidian installed for persistence?
- Was a runtime adapter configured? (hermes / custom)
- Which commands were run to verify?
- Which tests were run and their results?
- What files were created or modified?

Example report:

```
Installed AgentCore v0.1.0 from GitHub (pip install).
db-obsidian v0.2.1 was already installed.
Runtime: Hermes Desktop (hermes -z mode, black-box).
Verified: python -c "import agentcore" → 0.1.0
Verified: argus --help → working
Tests: pytest tests/ -q → 971 passed, 3 skipped
Files changed: None (AgentCore installed externally).
Backend: InMemoryBackend (default — no persistent memory configured).
```

---

## 10. Quick reference card (copy-paste)

```bash
# Detect
python -c "import agentcore; print(agentcore.__version__)"
argus --help
python -c "import db_obsidian; print(db_obsidian.__version__)"

# Install
pip install "agentcore @ git+https://github.com/AngKool-Dev/agent-core.git"
pip install "agentcore[db-obsidian]"  # optional: persistent memory

# Verify
pytest tests/ -q
ruff check .
ruff format --check .

# Obsess
argus task list
argus task show <task_id>
argus task events <task_id> --limit 50
argus task memories <task_id> --min-confidence VERIFIED
argus memory search "<query>" --json
argus memory show <memory_id>
argus memory confidence <memory_id>
```

---

## Key takeaways for AI agents

1. **Inspect before installing.** Always check the project first.
2. **Install only if authorized.** User permission is required for package installation.
3. **Start simple.** Use InMemoryBackend unless persistent memory is explicitly requested.
4. **Don't disrupt the host.** AgentCore wraps the existing runtime; it does not replace it.
5. **Verify everything.** Run tests, check CLI, confirm imports.
6. **Report transparently.** Document what was changed and what was verified.
