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
- Discovers skills from configurable directories (project-local, user-level, or via `AGENTCORE_SKILLS_PATH` env var)
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
- Verification scope controls which files are considered for file-scoped checks, while check flags control which checks run at all

#### Verification Scope vs Check Scope

AgentCore distinguishes between two orthogonal concepts:

| Concept | Controls | Values |
|---|---|---|
| **Verification scope** | Which files are in scope for file-scoped checks | `"project"` (default), `"changed-files"` |
| **Check scope** | Which verification checks are enabled | `run_format_check`, `run_build_check`, `run_tests` |

**Verification scope** determines the set of files a check operates against:
- `"project"`: checks run against the entire repository (default)
- `"changed-files"`: checks run only against files changed during the task, computed as the delta from the task-start Git state

**Check scope** determines which checks execute:
- `run_format_check`: format/lint check
- `run_build_check`: build/compile check
- `run_tests`: test suite

Under `"changed-files"` scope, only the **format check** is file-scoped. Build and test checks remain project-wide because they validate repository-wide correctness. The `git diff --check` check always validates the entire repository for whitespace errors regardless of scope.

If Git is unavailable or snapshot capture fails, the verifier falls back to project-wide verification rather than silently skipping checks.

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
│   ├── config.py         # Configuration loading and typed config
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