# Contributing to AgentCore

Thank you for your interest in contributing to AgentCore! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and constructive. We welcome contributors of all backgrounds and experience levels.

## How to Contribute

### Reporting Bugs

Open an issue on GitHub with:
- A clear, descriptive title
- Steps to reproduce the bug
- Expected vs actual behavior
- Environment details (Python version, OS, runtime)

### Suggesting Features

Open an issue on GitHub with:
- A clear description of the problem you're solving
- Your proposed solution
- Any alternatives you've considered

### Development Setup

```bash
# Clone the repository
git clone https://github.com/agentcore/agent-core.git
cd agent-core

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Unix

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run the default test suite (fast, deterministic)
pytest tests/ -q

# Run real-runtime tests (requires Hermes installed)
$env:AGENTCORE_REAL_RUNTIME="1"  # PowerShell
# AGENTCORE_REAL_RUNTIME=1       # Bash
pytest -m real_runtime -q
```

### Code Style

- Follow PEP 8
- Use type hints for all public functions and methods
- Write docstrings for public APIs
- Keep changes focused and minimal

### Commit Messages

- Use present tense ("Add feature" not "Added feature")
- First line is a summary (50 chars or less)
- Optional body after a blank line for context

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -q`)
5. Commit your changes (`git commit -m "Add my feature"`)
6. Push to your fork (`git push origin feature/my-feature`)
7. Open a Pull Request

## Project Structure

```
agent-core/
├── agentcore/          # Core framework package
│   ├── agent.py        # Main agent orchestrator
│   ├── task.py         # Task state machine
│   ├── runtimes/       # Runtime adapters
│   ├── skills/         # Skill system
│   ├── memory/         # Memory backends
│   ├── cli/            # CLI interface
│   └── ...
├── tests/              # Test suite
├── docs/               # Documentation
└── examples/           # Usage examples
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
