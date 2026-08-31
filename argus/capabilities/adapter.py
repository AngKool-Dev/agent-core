"""Capability adapter for existing Argus tools."""

from typing import Any, Dict, List, Optional

from argus.capabilities import (
    Capability,
    CapabilityMetadata,
    CapabilitySchema,
    CapabilityType,
)
from argus.tools import Tool, ToolResult
from argus.tools.file import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from argus.tools.bash import BashTool


def create_tool_capability(tool: Tool, capability_id: str = None) -> Capability:
    """Wrap an existing Argus Tool into a Capability."""
    cap_id = capability_id or tool.name
    cap_type = _infer_type(tool.name)

    schema = CapabilitySchema(
        name=cap_id,
        description=tool.description,
        parameters={"type": "object"},
        required_parameters=_required_params(tool.name),
    )

    metadata = CapabilityMetadata(
        id=cap_id,
        name=cap_id,
        description=tool.description,
        type=cap_type,
        schema=schema,
    )

    return ToolCapabilityAdapter(metadata, tool)


class ToolCapabilityAdapter(Capability):
    def __init__(self, metadata: CapabilityMetadata, tool: Tool):
        super().__init__(metadata)
        self._tool = tool

    def check_availability(self) -> bool:
        return self.metadata.availability

    def health_check(self) -> Dict[str, Any]:
        try:
            result = self._execute_minimal()
            return {
                "status": "healthy" if result.success else "unhealthy",
                "message": result.output if result.success else result.error,
                "last_check": __import__("time").time(),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "last_check": __import__("time").time(),
            }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            result = self._tool.execute(**input_data)
            duration = time.time() - start
            return {
                "success": result.success,
                "output": result.to_dict(),
                "error": result.error,
                "execution_time": duration,
                "backend": self._tool.name,
                "fallback_used": False,
            }
        except Exception as e:
            duration = time.time() - start
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "execution_time": duration,
                "backend": self._tool.name,
                "fallback_used": False,
            }

    def _execute_minimal(self) -> ToolResult:
        """Execute a minimal command to check tool health."""
        if self._tool.name == "bash":
            return self._tool.execute(command="echo ok")
        elif self._tool.name == "read_file":
            return self._tool.execute(path=str(__import__("pathlib").Path.home()))
        elif self._tool.name == "list_dir":
            return self._tool.execute(path=".")
        elif self._tool.name == "grep":
            return self._tool.execute(pattern="", path=".")
        elif self._tool.name == "glob":
            return self._tool.execute(pattern="*")
        elif self._tool.name == "git_status":
            return self._tool.execute(project_path=".")
        else:
            return self._tool.execute()


def register_default_tool_capabilities(registry, tool_registry) -> None:
    """Register all built-in tool capabilities into the capability registry."""
    from argus.tools.git import (
        GitAddTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool, GitWorkflowTool,
    )
    from argus.tools.memory import MemoryAddTool, MemorySearchTool
    from argus.tools.search import GlobTool, GrepTool
    from argus.tools.browser import BrowserTool

    tool_map = [
        (ReadFileTool(), "filesystem.read", "Read a file from the filesystem"),
        (WriteFileTool(), "filesystem.write", "Write content to a file"),
        (EditFileTool(), "filesystem.edit", "Edit a file by replacing old_string with new_string"),
        (ListDirTool(), "filesystem.list_dir", "List directory contents"),
        (BashTool(), "shell.execute", "Execute a shell command"),
        (GrepTool(), "search.grep", "Search file contents using grep"),
        (GlobTool(), "search.glob", "Search for files by pattern"),
        (GitStatusTool(), "git.status", "Show git working tree status"),
        (GitDiffTool(), "git.diff", "Show git diff"),
        (GitLogTool(), "git.log", "Show git commit log"),
        (GitAddTool(), "git.add", "Stage files for commit"),
        (GitCommitTool(), "git.commit", "Record changes to git"),
        (GitWorkflowTool(), "git.workflow", "Git workflow automation"),
        (MemoryAddTool(), "memory.store", "Store a memory entry"),
        (MemorySearchTool(), "memory.search", "Search memory entries"),
        (BrowserTool(), "browser.navigate", "Web browser automation"),
    ]

    for tool, cap_id, description in tool_map:
        try:
            tool_registry.register(tool)
            cap = create_tool_capability(tool, cap_id)
            registry.register(cap)
        except Exception:
            pass


def _infer_type(tool_name: str) -> CapabilityType:
    if tool_name in ("read_file", "list_dir"):
        return CapabilityType.READ
    elif tool_name in ("write_file", "edit_file"):
        return CapabilityType.WRITE
    elif tool_name in ("bash",):
        return CapabilityType.EXECUTE
    elif tool_name in ("grep", "glob"):
        return CapabilityType.SEARCH
    elif tool_name in ("browser",):
        return CapabilityType.BROWSER
    elif tool_name in ("git_status", "git_diff", "git_log", "git_add", "git_commit", "git_workflow"):
        return CapabilityType.GIT
    elif tool_name in ("memory_add", "memory_search"):
        return CapabilityType.MEMORY
    else:
        return CapabilityType.EXECUTE


def _required_params(tool_name: str) -> List[str]:
    return {
        "read_file": ["path"],
        "write_file": ["path", "content"],
        "edit_file": ["path", "old_string", "new_string"],
        "list_dir": ["path"],
        "bash": ["command"],
        "grep": ["pattern", "path"],
        "glob": ["pattern"],
        "git_status": [],
        "git_diff": [],
        "git_log": [],
        "git_add": ["paths"],
        "git_commit": ["message"],
        "git_workflow": ["stage"],
        "memory_add": ["content"],
        "memory_search": ["query"],
        "browser": ["action"],
    }.get(tool_name, [])
