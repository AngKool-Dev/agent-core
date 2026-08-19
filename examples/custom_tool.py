"""
Custom tool registration example.

Demonstrates how to add a custom tool to AgentCore's ToolManager.
"""

from pathlib import Path

from agentcore.tools import ToolManager, ToolResult


def my_custom_tool(args: dict, work_dir: Path, start: float) -> ToolResult:
    """
    Example custom tool that counts lines in a file.

    Args:
        args: Tool arguments dict (expects 'path' key)
        work_dir: Working directory for the tool
        start: Start time for duration calculation

    Returns:
        ToolResult with the line count
    """
    file_path = args.get("path", "")
    if not file_path:
        return ToolResult(
            success=False,
            tool="line_counter",
            output="",
            error="Missing 'path' argument",
            exit_code=1,
            duration=0.0,
        )

    full_path = Path(file_path)
    if not full_path.is_absolute():
        full_path = work_dir / file_path

    if not full_path.exists():
        return ToolResult(
            success=False,
            tool="line_counter",
            output="",
            error=f"File not found: {file_path}",
            exit_code=1,
            duration=0.0,
        )

    try:
        content = full_path.read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        return ToolResult(
            success=True,
            tool="line_counter",
            output=f"{line_count} lines in {file_path}",
            error="",
            exit_code=0,
            duration=0.0,
        )
    except Exception as e:
        return ToolResult(
            success=False,
            tool="line_counter",
            output="",
            error=str(e),
            exit_code=1,
            duration=0.0,
        )


def register_tool(manager: ToolManager) -> None:
    """Register the custom tool with a ToolManager instance."""
    manager.register_tool("line_counter", my_custom_tool)


def main():
    manager = ToolManager(project_path=".")

    # Register the custom tool
    register_tool(manager)

    # Execute the custom tool via the standard dispatch interface
    from agentcore.runtimes.base import ToolCall

    tool_call = ToolCall(tool="line_counter", arguments={"path": "README.md"})
    result = manager.execute(tool_call)

    print(f"Tool: {tool_call.tool}")
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Error: {result.error}")


if __name__ == "__main__":
    main()
