# AgentCore V0.1 Architecture

## Overview

AgentCore is a universal AI coding-agent framework with pluggable runtime adapters.

## Core Components

```
                    USER
                     │
                     ▼
              ┌─────────────┐
              │  AgentCore  │
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
              Runtime Adapter
                     │
                     ▼
                  Hermes
```

## Key Design Principles

1. **Runtime Independence**: The agent brain is separate from the runtime.
2. **Pluggable Architecture**: New runtimes (Kilo, OpenCode) can be added without changing core.
3. **Skill Composition**: Skills are discovered and composed automatically.
4. **Structured State**: All task state is serializable for persistence.
5. **Investigation-First**: The agent investigates before acting.

## Components

### Task Model
- Structured representation of agent work
- Serializable state transitions
- Hypothesis tracking
- Verification state

### Skill System
- Discovers skills from paths in `argus.toml` (default: `argus/skills/builtin`)
- Automatic routing based on prompt analysis
- Supports multiple skills per task

### Memory
- Abstract interface (`MemoryManager`)
- DB-Obsidian adapter available
- Project and session persistence

### Runtime Adapter
- Abstract interface (`RuntimeAdapter`)
- Hermes implementation (`HermesRuntime`)
- Pluggable for Kilo, OpenCode

### Verifier
- Project-type aware checks
- Format, build, and test verification
- Failure classification

## Directory Structure

```
agent-core/
├── agentcore/
│   ├── __init__.py
│   ├── agent.py          # Main agent orchestrator
│   ├── task.py           # Task model and states
│   ├── planner.py        # Plan generation and adaptation
│   ├── router.py         # Skill routing
│   ├── context.py        # Project context discovery
│   ├── memory.py         # Memory abstraction
│   ├── verifier.py       # Verification system
│   ├── tools.py          # Tool execution
│   ├── runtimes/         # Runtime adapters
│   │   ├── __init__.py
│   │   ├── base.py       # Abstract runtime interface
│   │   └── hermes.py     # Hermes implementation
│   └── skills/           # Skill system
│       ├── __init__.py
│       ├── loader.py     # Skill content loader
│       └── registry.py   # Skill discovery and registry
├── cli/
│   ├── __init__.py
│   └── main.py           # CLI entry point
├── tests/
├── config/
│   └── agent.toml        # Configuration
├── docs/
│   ├── architecture.md
│   └── runtime-adapters.md
├── README.md
└── pyproject.toml
```