# AgentCore V0.1

Universal AI coding-agent framework with pluggable runtime adapters.

## The Principle

**THE AGENT BRAIN IS SEPARATE FROM THE AGENT RUNTIME.**

Hermes is the first runtime. Kilo and OpenCode can be added later as interchangeable engines underneath the same system.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Run a task in the current directory
agent "Fix the launcher crash"

# Use a specific project
agent -p /path/to/project "Why does launch fail?"

# Use a specific runtime/model
agent -r hermes -m claude-sonnet-4 "Implement X"
```

## Components

| Component | Purpose |
|-----------|---------|
| `agent.py` | Main orchestrator - runs the agent loop |
| `task.py` | Task model with states and serialization |
| `router.py` | Automatic skill routing |
| `context.py` | Project context discovery |
| `memory.py` | Memory abstraction layer |
| `verifier.py` | Project-appropriate verification |
| `tools.py` | Controlled tool execution |
| `config.py` | Configuration loading and typed config |
| `runtimes/base.py` | Abstract runtime interface |
| `runtimes/hermes.py` | Hermes runtime adapter |
| `skills/` | Skill registry and loader |

## Architecture

```
User → AgentCore → Runtime Adapter (Hermes) → Tools
```

The agent brain owns:
- Task state
- Skill routing
- Project context
- Memory
- Planning
- Verification

The runtime adapter owns:
- Model invocation
- Tool definition
- Session management

## Skill System

Skills are discovered from configurable directories. By default, AgentCore searches:
- A `skills/` directory in the project
- A user-level skills directory (`~/.agentcore/skills/` on Linux/macOS,
  `%LOCALAPPDATA%\agentcore\skills` on Windows)

You can override skill discovery with the `AGENTCORE_SKILLS_PATH` environment
variable (use the OS path separator, `:` on Linux/macOS, `;` on Windows, to
list multiple directories):

```bash
export AGENTCORE_SKILLS_PATH="/custom/skills:/more/skills"
agent "Fix the crash"
```

Or configure paths in `config/agent.toml`:

```toml
[skill_paths]
primary = "~/.agentcore/skills"
extra = ["/path/to/more/skills"]
```

Available skills include:
- `debugging-and-error-recovery` - Systematic bug fixing
- `test-driven-development` - Test-driven development
- `documentation-and-adrs` - Documentation and architecture decisions
- `code-review-and-quality` - Code review guidance
- And many more...

## Memory Integration

AgentCore uses DB-Obsidian for persistent memory via a clean abstraction:

```python
from agentcore.memory import MemoryManager
from agentcore.adapters.memory_dbobsidian import DBObsidianBackend

backend = DBObsidianBackend(db_path="~/.agentcore/memory.db")
memory = MemoryManager(backend)

# Search memories
results = memory.search("decision", project="my-project")

# Store information
memory.store_decision("Use async patterns", project="my-project")
```

## Configuration

AgentCore loads configuration from TOML files in a deterministic order
(first match wins):

1. Explicit config via CLI: `agent --config path/to/agentcore.toml`
2. Project-local: `./agentcore.toml` or `./config/agentcore.toml`
3. User-level: `{user_config_dir}/agentcore.toml`
4. Built-in defaults

Full example (`config/agent.toml`):

```toml
[agent]
default_runtime = "hermes"

[skill_paths]
primary = "~/.agentcore/skills"

[memory]
backend = "db_obsidian"
db_path = "~/.agentcore/memory.db"

[tool_limits]
max_iterations = 10
max_tool_calls = 20
timeout = 300

[verification]
run_format_check = true
run_build_check = true
run_tests = true

[project_discovery]
max_context_files = 50
exclude_patterns = ["*.pyc", "__pycache__", ".git", "node_modules"]
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## Future Roadmap

- V0.2: Better planning, parallel tool execution
- V0.3: Advanced memory, semantic retrieval
- V0.4: Automatic lesson extraction
- V0.5: Kilo and OpenCode runtime adapters
- V1.0: Full autonomous coding workflow

## License

MIT