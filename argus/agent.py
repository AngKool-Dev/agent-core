"""Argus agent integration with AgentCore."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentcore import Agent, AgentConfig, MemoryManager, create_agent
from agentcore.runtimes.base import RuntimeAdapter
from agentcore.runtimes.hermes import HermesRuntime


class ArgusAgent:
    def __init__(
        self,
        project_path: Optional[Union[str, Path]] = None,
        runtime: Optional[RuntimeAdapter] = None,
        memory: Optional[MemoryManager] = None,
        config: Optional[AgentConfig] = None,
    ):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.runtime = runtime or HermesRuntime()
        self.memory = memory
        self.config = config or AgentConfig()

        self._agent = create_agent(
            runtime=self.runtime,
            memory=self.memory,
            project_path=self.project_path,
            config=self.config,
        )
        self._last_result: Optional[Dict[str, Any]] = None

    def execute(self, request: str) -> Dict[str, Any]:
        self._last_result = self._agent.execute(request, str(self.project_path))
        return self._last_result

    def status(self) -> Dict[str, Any]:
        if not self._last_result:
            return {"status": "idle"}

        task = self._last_result.get("task", {})
        return {
            "status": task.get("current_state", "unknown"),
            "task_id": task.get("task_id"),
            "tools_used": task.get("tools_used", 0),
            "iterations": task.get("iterations", 0),
            "skills": task.get("selected_skills", []),
            "success": self._last_result.get("success", False),
        }

    def last_result(self) -> Optional[Dict[str, Any]]:
        return self._last_result

    def switch_project(self, project_path: Union[str, Path]) -> None:
        self.project_path = Path(project_path)
        self._agent = create_agent(
            runtime=self.runtime,
            memory=self.memory,
            project_path=self.project_path,
            config=self.config,
        )
        self._last_result = None
