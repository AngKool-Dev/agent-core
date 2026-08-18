# AgentCore

Universal AI coding-agent framework with pluggable runtime adapters.

## The Principle

**THE AGENT BRAIN IS SEPARATE FROM THE AGENT RUNTIME.**

AgentCore provides the orchestration layer: task state management, skill routing,
project context, memory, planning, verification, and tool execution.

Runtimes are interchangeable plug-ins. Hermes is the first runtime. Kilo and
OpenCode can be added later without changing AgentCore's core logic.

## Installation

```bash
pip install agentcore
```

For development:

```bash
git clone https://github.com/agentcore/agent-core.git
cd agent-core
pip install -e ".[dev]"
```

## Quick Start

```bash
# Run a task in the current directory
agent "Fix the launcher crash"

# Use a specific project
agent -p /path/to/project "Why does launch fail?"

# Use a specific runtime
agent -r hermes -m claude-sonnet-4 "Implement X"

# List available runtimes
agent --list-runtimes
```

## Python API

```python
from agentcore import Agent, AgentConfig

config = AgentConfig(max_iterations=10, enable_verification=True)
agent = Agent(runtime=my_runtime, memory=my_memory, config=config)
result = agent.execute("Fix the failing tests")
```

## Runtime Discovery

AgentCore ships with a runtime registry. List available runtimes:

```bash
agent --list-runtimes
```

Output:

```
Available runtimes:

  hermes
    description: Hermes CLI runtime (hermes -z)
    capabilities:
      text generation:       yes
      structured tool calls: no
      external tool exec:    no
      streaming:             no
      cancellation:          no
```

## Configuration

AgentCore loads configuration from TOML files in priority order:

1. Explicit config: `agent --config path/to/agentcore.toml`
2. Project-local: `./agentcore.toml` or `./config/agentcore.toml`
3. User-level: `{user_config_dir}/agentcore.toml`
4. Built-in defaults

Example `agentcore.toml`:

```toml
[agent]
runtime = "hermes"
model = "auto"

[verification]
scope = "project"
run_format_check = true
run_build_check = true
run_tests = true

[skill_paths]
primary = "~/.agentcore/skills"

[memory]
backend = "in_memory"
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
    # Your tool logic here
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
|------|---------|----------|
| Unit | Mocked | ✅ |
| Integration | Deterministic/mock | ✅ |
| Real runtime | Hermes/Kilo/OpenCode | ❌ |

The default `pytest -q` suite runs only unit and deterministic integration tests. Real-runtime tests are explicitly opt-in.

## Documentation

- `docs/architecture.md` — System architecture and design
- `docs/runtime-adapters.md` — Runtime adapter interface and capability contract

## License

MIT
