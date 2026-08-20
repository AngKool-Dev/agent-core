# Runtime Adapters

AgentCore supports multiple runtime adapters through a common interface.

## Interface

The `RuntimeAdapter` abstract class defines the interface:

```python
class RuntimeAdapter(ABC):
    @abstractmethod
    def send(prompt: str, context: dict, tools: list[str] | None) -> dict[str, Any]:
        """Send prompt/context to the model runtime."""
    
    @abstractmethod
    def receive_tool_request() -> Optional[ToolRequest]:
        """Receive tool/action requests from the model."""
    
    @abstractmethod
    def execute_tool(tool_request: ToolRequest) -> ToolResult:
        """Execute a tool request."""
    
    @abstractmethod
    def get_response() -> str:
        """Get the model's response."""
    
    @abstractmethod
    def is_complete() -> bool:
        """Check if the task is complete."""
```

## Available Adapters

### Hermes Runtime

The first implementation, using the Hermes CLI:

```python
runtime = HermesRuntime(model="claude-sonnet-4", provider="anthropic")
```

Features:
- Uses `hermes -z` for one-shot execution
- Supports model and provider overrides
- Automatic tool integration

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