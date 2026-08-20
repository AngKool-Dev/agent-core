"""Argus native runtime using AgentCore."""

from pathlib import Path
from typing import Any, Dict, Optional

from agentcore import Agent, AgentConfig, MemoryManager, create_agent
from agentcore.runtimes.base import RuntimeAdapter, ToolCall, ToolResult


class NativeRuntime(RuntimeAdapter):
    def __init__(
        self,
        project_path: Optional[str] = None,
        model: Optional[str] = None,
        config: Optional[AgentConfig] = None,
    ):
        self._project_path = Path(project_path) if project_path else Path.cwd()
        self._model = model
        self._agent_config = config or AgentConfig()
        self._agent: Optional[Agent] = None
        self._pending_tool: Optional[ToolCall] = None
        self._memory: Optional[MemoryManager] = None

    def _get_or_create_agent(self) -> Agent:
        if not self._agent:
            runtime = self._create_runtime()
            memory = self._get_or_create_memory()
            self._agent = create_agent(
                runtime=runtime,
                memory=memory,
                project_path=self._project_path,
                config=self._agent_config,
            )
        return self._agent

    def _create_runtime(self):
        try:
            from agentcore.runtimes.hermes import create_hermes_runtime
            return create_hermes_runtime(model=self._model)
        except Exception:
            from agentcore.runtimes.base import RuntimeAdapter
            return _FallbackRuntime()

    def _get_or_create_memory(self) -> MemoryManager:
        if not self._memory:
            try:
                from agentcore.adapters.memory_dbobsidian import DBObsidianBackend
                backend = DBObsidianBackend()
                self._memory = MemoryManager(backend)
            except Exception:
                backend = _InMemoryBackend()
                self._memory = MemoryManager(backend)
        return self._memory

    def respond(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self._get_or_create_agent()
        result = agent.execute(context.get("user_request", ""), str(self._project_path))
        return {
            "complete": result.get("task", {}).get("current_state") in ("COMPLETED", "FAILED"),
            "response": str(result.get("task", {}).get("current_state")),
            "tool_calls": [],
        }

    def execute_tool(self, tool_call: ToolCall, project_path: str) -> ToolResult:
        self._pending_tool = tool_call
        return ToolResult(call_id=tool_call.call_id, success=False, error="Tool execution delegated to Argus")

    def get_pending_tool_call(self) -> Optional[ToolCall]:
        return self._pending_tool

    def clear_tool_call(self) -> None:
        self._pending_tool = None


class _FallbackRuntime:
    def respond(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"complete": True, "response": "Fallback runtime: no model available", "tool_calls": []}

    def execute_tool(self, tool_call, project_path):
        return ToolResult(call_id=tool_call.call_id, success=False, error="No runtime configured")


class _InMemoryBackend:
    def __init__(self):
        self._store = []

    def search(self, query, project=None, limit=20):
        return [m for m in self._store if query.lower() in m.get("content", "").lower()]

    def store(self, type, content, project=None, importance=0.5):
        mem = {"id": f"mem-{len(self._store)}", "type": type, "content": content, "project": project}
        self._store.append(mem)
        return mem

    def update(self, memory_id, content):
        for m in self._store:
            if m["id"] == memory_id:
                m["content"] = content
                return m
        return {}

    def list(self, project=None, type=None, limit=50):
        return self._store
