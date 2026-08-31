# ARGUS 1.0.0

Universal AI coding-agent framework with security-first execution, durable operations, and pluggable runtime adapters.

## What is ARGUS?

ARGUS is a capability-based AI coding agent framework that enforces security at every level of execution. It provides:

- **Security-first execution**: MODEL → CAPABILITY ROUTER → SECURITY POLICY → ALLOW/ASK/DENY → EXECUTION
- **Durable execution**: Journaled operations with crash recovery and reconciliation
- **Replay/Forensics**: Observational replay of past executions for debugging and auditing
- **Provider resilience**: Circuit breakers, retry policies, and fallback providers
- **MCP support**: Integration with Model Context Protocol servers
- **Benchmarking**: Scientific evaluation of agent performance

## Installation

### From Source

```bash
git clone https://github.com/AngKool-Dev/agent-core.git
cd agent-core
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# Run ARGUS CLI
argus --help

# Check version
argus --version

# Run with a project
argus -p /path/to/project "Your task here"

# Run in REPL mode
argus
```

## Configuration

ARGUS uses a configuration file (default: `argus.toml`):

```toml
[model]
provider = "ollama"
name = "llama3"

[gateway]
base_url = "https://your-gateway.example.com"
api_key = "your-api-key"
```

## Provider Setup

ARGUS supports multiple LLM providers:

- **Ollama**: Local models (default)
- **OpenRouter**: Cloud models
- **Gemini**: Google's Gemini models
- **Groq**: Fast inference
- **Cerebras**: High-performance inference

Configure providers in your `argus.toml` or via environment variables.

## MCP Setup

ARGUS supports Model Context Protocol (MCP) servers for extended capabilities:

```toml
[mcp.servers.my-server]
command = "my-mcp-server"
args = ["--option", "value"]
```

## Security Model

ARGUS enforces a security-first execution model:

1. **DENY** cannot execute
2. **ASK** requires human approval
3. Approval scope cannot expand
4. Sandbox remains authoritative
5. MCP cannot bypass security
6. Provider fallback cannot bypass security
7. Recovery cannot bypass security
8. Replay cannot execute
9. Secrets cannot enter persisted model-visible state

## Crash Recovery

ARGUS provides durable execution with automatic crash recovery:

- Operations are journaled before execution
- Crashes are detected automatically
- State is reconciled after recovery
- Recovery budget prevents infinite loops

## Replay

ARGUS can replay past executions for debugging and auditing:

```bash
argus replay <run-id>
```

Replay is observational only - it cannot execute operations.

## Benchmarking

ARGUS includes a scientific benchmarking framework:

```bash
argus benchmark
```

## Troubleshooting

### Common Issues

1. **CLI not found**: Ensure the package is installed and the scripts directory is in your PATH
2. **Provider errors**: Check your provider configuration and API keys
3. **MCP errors**: Verify MCP server configuration and connectivity

### Getting Help

- Check the documentation in `docs/`
- Review the `CHANGELOG.md`
- Open an issue on GitHub

## Known Limitations

- External provider tests require opt-in credentials
- Long-duration stability tests not executed in CI
- Platform-specific tests may vary outside Windows
- Build reproducibility is semantic (timestamps vary)

## Reporting Security Issues

Please see [SECURITY.md](SECURITY.md) for information on reporting security vulnerabilities.

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned future work.
