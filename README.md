# AgentCore V0.1

Universal AI coding-agent framework with pluggable runtime adapters.

## The Principle

**THE AGENT BRAIN IS SEPARATE FROM THE AGENT RUNTIME.**

Hermes is the first runtime. Kilo and OpenCode can be added later as interchangeable engines underneath the same system.

## Installation

```bash
cd /home/era/agent-core
pip install -e .
```

## Quick Start

```bash
# Run a task
agent "Fix the launcher crash"

# Use a specific project
agent -p /home/era/Projects/EraLauncher "Why does launch fail?"

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

Skills are discovered from `D:/agent-core/unified_folder/ObsidianVault/agent-skills/skills` and automatically composed based on user prompts.

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

Configuration is in `config/agent.toml`:

```toml
default_runtime = "hermes"
max_iterations = 10
max_tools = 20
timeout_seconds = 300
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