"""Memory tools for Argus."""

from typing import Any, Dict, Optional

from . import Tool, ToolResult


class MemoryAddTool(Tool):
    name = "memory_add"
    description = "Store an observation, decision, lesson, or architecture note in project memory"

    def execute(
        self,
        summary: str,
        details: str = "",
        entry_type: str = "observation",
        importance: float = 0.5,
        **kwargs,
    ) -> ToolResult:
        try:
            from argus.agent import ArgusAgent

            agent = _get_agent()
            if agent is None:
                return ToolResult(tool=self.name, success=False, error="Memory is not available")

            result = agent.memory.add_observation(
                summary=summary,
                details=details,
                entry_type=entry_type,
                importance=importance,
            )
            if result:
                return ToolResult(tool=self.name, success=True, output=f"Memory stored: {summary}")
            return ToolResult(tool=self.name, success=False, error="Failed to store memory")
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search project memory for relevant past knowledge"

    def execute(self, query: str, limit: int = 5, **kwargs) -> ToolResult:
        try:
            from argus.agent import ArgusAgent

            agent = _get_agent()
            if agent is None:
                return ToolResult(tool=self.name, success=False, error="Memory is not available")

            results = agent.memory.search(query, limit=limit)
            if not results:
                return ToolResult(tool=self.name, success=True, output="No relevant memory found")

            lines = []
            for r in results:
                lines.append(f"[{r.get('type', '')}] {r.get('summary', r.get('content', ''))}")
                if r.get("content") and len(r["content"]) > 100:
                    lines.append(f"  {r['content'][:200]}...")
            return ToolResult(tool=self.name, success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))


_agent_ref = None


def _get_agent():
    return _agent_ref


def set_agent(agent):
    global _agent_ref
    _agent_ref = agent
