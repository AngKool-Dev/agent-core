# Runtime Adapters

AgentCore supports multiple runtime adapters through a common interface.

## RuntimeAdapter Interface

The `RuntimeAdapter` abstract class defines the interface:

```python
class RuntimeAdapter(ABC):
    @abstractmethod
    def respond(self, context: dict[str, Any]) -> RuntimeResponse:
        """Send prompt/context to the model runtime and return a structured response."""

    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Return a dict describing what this runtime supports."""

    def cancel(self) -> None:
        """Request cancellation of an in-flight request. Default: no-op."""

    @property
    def default_model(self) -> Optional[str]:
        """Return the default model name, if any."""
        return None
```

## RuntimeResponse Contract

All runtimes must return a `RuntimeResponse`:

```python
@dataclass
class RuntimeResponse:
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    metadata: dict[str, Any] = field(default_factory=dict)
```

`FinishReason` values:
- `STOP` — Model produced final text, no more work needed
- `TOOL_CALLS` — Model requested tool calls
- `TIMEOUT` — Runtime timed out
- `ERROR` — Runtime error occurred

## Capability Contract

Runtimes advertise their capabilities via the `capabilities()` method. The following keys are standardized:

| Key | Type | Meaning |
|---|---|---|
| `text_generation` | `bool` | Runtime can produce text responses |
| `tool_calls` | `bool` | Runtime exposes structured `ToolCall` objects to AgentCore |
| `external_tool_execution` | `bool` | AgentCore is responsible for executing those tools |
| `streaming` | `bool` | Runtime supports streaming responses |
| `cancellation` | `bool` | Runtime supports cancellation |

Additional metadata keys (runtime-specific) are allowed, such as `adapter`, `model`, `provider`, and `timeout`.

### Tool Execution Ownership

The capability contract distinguishes two runtime categories:

**Tool-aware runtime** (`tool_calls=True`, `external_tool_execution=True`):
- Runtime exposes structured `ToolCall` objects in `RuntimeResponse.tool_calls`
- AgentCore executes those tools via `ToolManager`
- AgentCore handles observation, replanning, and verification after tool execution

**Black-box runtime** (`tool_calls=False`, `external_tool_execution=False`):
- Runtime owns tool execution internally
- `RuntimeResponse.tool_calls` is always empty
- AgentCore receives only the final text response
- No tool-execution state transitions occur in the Agent loop

### HermesRuntime Example

Hermes v0.20.2 `-z` mode is a black-box runtime:

```python
rt = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
caps = rt.capabilities()
# {
#     "text_generation": True,
#     "tool_calls": False,
#     "external_tool_execution": False,
#     "streaming": False,
#     "cancellation": False,
#     "adapter": "hermes",
#     "model": "claude-sonnet-4",
#     "provider": "anthropic",
#     "timeout": 300,
# }
```

Hermes internally executes tools and returns only the synthesized final text. AgentCore sees `tool_calls=[]` and skips the tool-execution state machine.

## Available Adapters

### Hermes Runtime

The first implementation, using the Hermes CLI:

```python
runtime = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
```

Features:
- Uses `hermes -z` for one-shot execution
- Supports model and provider overrides
- Black-box text runtime (tools executed internally by Hermes)

### Future Adapters

#### Kilo Runtime
- Uses Kilo's chat and tool system
- Supports Claude Code-style tool calls
- Direct session communication

#### OpenCode Runtime
- Uses OpenCode's ACP protocol
- Supports agent-to-agent communication
- Persistent session management

## Adding a New Runtime

1. Create a new file in `agentcore/runtimes/`
2. Implement the `RuntimeAdapter` interface
3. Export from `runtimes/__init__.py`
4. Add to CLI choices

The core agent code remains unchanged.
