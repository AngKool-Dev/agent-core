"""Argus interactive REPL."""

import os
import sys
from pathlib import Path
from typing import Optional

from argus.agent import ArgusAgent, ArgusAgentConfig
from argus.commands import build_registry
from argus.config import ArgusConfig
from argus.model import create_model_from_config
from argus.permissions import PermissionConfig
from argus.session import SessionManager
from argus.tools import ToolRegistry
from argus.tools.bash import BashTool
from argus.tools.file import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from argus.tools.search import GlobTool, GrepTool
from argus.tools.git import GitAddTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool


class ArgusREPL:
    def __init__(
        self,
        project_path: Optional[Path] = None,
        config: Optional[ArgusConfig] = None,
    ):
        self.project_path = project_path or Path.cwd()
        self.config = config or ArgusConfig()

        permissions = PermissionConfig(
            read=self.config.get("permissions.read", "allow"),
            search=self.config.get("permissions.search", "allow"),
            write=self.config.get("permissions.write", "ask"),
            bash=self.config.get("permissions.bash", "ask"),
            git=self.config.get("permissions.git", "ask"),
            browser=self.config.get("permissions.browser", "ask"),
        )

        self.tool_registry = ToolRegistry(
            permissions=permissions,
            ask_callback=self._permission_prompt,
        )
        self._register_tools()

        self.session_manager = SessionManager(
            self.config.get("memory.session_location", "~/.agentcore/sessions")
        )
        self.session = None

        self.agent = ArgusAgent(
            project_path=self.project_path,
            config=self._build_agent_config(),
            status_callback=self._status_update,
            model=self._build_model(),
        )

        self.commands = build_registry()
        self._running = False
        self._last_status = ""

    def _register_tools(self) -> None:
        self.tool_registry.register(ReadFileTool())
        self.tool_registry.register(WriteFileTool())
        self.tool_registry.register(EditFileTool())
        self.tool_registry.register(ListDirTool())
        self.tool_registry.register(BashTool())
        self.tool_registry.register(GrepTool())
        self.tool_registry.register(GlobTool())
        self.tool_registry.register(GitStatusTool())
        self.tool_registry.register(GitDiffTool())
        self.tool_registry.register(GitLogTool())
        self.tool_registry.register(GitAddTool())
        self.tool_registry.register(GitCommitTool())

    def _build_agent_config(self) -> ArgusAgentConfig:
        return ArgusAgentConfig(
            max_iterations=self.config.get("agent.max_iterations", 10),
            max_tool_calls=self.config.get("agent.max_tools", 20),
            max_runtime_seconds=self.config.get("agent.timeout_seconds", 300),
            model=self.config.get("model.name"),
            provider=self.config.get("model.provider"),
        )

    def _build_model(self):
        model_config = {
            "provider": self.config.get("model.provider", "ollama"),
            "name": self.config.get("model.name", "llama3"),
        }
        if self.config.get("model.api_key"):
            model_config["api_key"] = self.config.get("model.api_key")
        if self.config.get("model.base_url"):
            model_config["base_url"] = self.config.get("model.base_url")
        return create_model_from_config(model_config)

    def _permission_prompt(self, prompt: str, tool: str) -> bool:
        print(f"\n[PERMISSION] {prompt}")
        answer = input("Allow? [y/N]: ").strip().lower()
        return answer == "y"

    def _status_update(self, message: str) -> None:
        self._last_status = message
        sys.stdout.write(f"\r\033[K> {message}")
        sys.stdout.flush()

    def _clear_status(self) -> None:
        if self._last_status:
            sys.stdout.write(f"\r\033[K")
            sys.stdout.flush()
            self._last_status = ""

    def run(self) -> int:
        self._running = True
        prompt = self.config.get("repl.prompt", "argus> ")

        if not self.session:
            default_name = f"session-{self.project_path.name}"
            self.session = self.session_manager.create(default_name, str(self.project_path))

        print("Argus v0.1.0 — Type /help for commands, /agent <request> to run the agent")
        print(f"Project: {self.project_path}")
        print(f"Session: {self.session.name}")
        print()

        while self._running:
            try:
                try:
                    self._clear_status()
                    line = input(prompt)
                except EOFError:
                    break

                line = line.strip()
                if not line:
                    continue

                if line.startswith("/"):
                    response = self._handle_command(line)
                    if response:
                        print(response)
                else:
                    self._handle_message(line)

            except KeyboardInterrupt:
                print()
                continue
            except SystemExit:
                break
            except Exception as e:
                print(f"Error: {e}")

        self.session_manager.save_current()
        return 0

    def _handle_command(self, line: str) -> str:
        parts = line[1:].split()
        if not parts:
            return ""
        command = parts[0]
        args = parts[1:]
        return self.commands.handle(command, self, args)

    def _handle_message(self, message: str) -> None:
        self.session.add_message("user", message)

        try:
            result = self.agent.execute(message)
            self._clear_status()
            response = self._format_result(result)
            print(response)
            self.session.add_message("assistant", response, result=result)
        except Exception as e:
            self._clear_status()
            error_msg = f"Error: {e}"
            print(error_msg)
            self.session.add_message("assistant", error_msg, error=str(e))

    def _format_result(self, result: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"Task: {result.get('task_id', 'N/A')}")
        lines.append(f"State: {result.get('status', 'N/A')}")
        lines.append(f"Iterations: {result.get('iterations', 0)}")
        lines.append(f"Tools used: {result.get('tools_used', 0)}")

        plan = result.get("plan", [])
        if plan:
            lines.append("Plan:")
            for step in plan:
                status = "done" if step.get("completed") else "pending"
                lines.append(f"  [{status}] {step.get('action')}: {step.get('description')}")

        tool_results = result.get("tool_results", [])
        if tool_results:
            lines.append("Recent tool results:")
            for tr in tool_results[-3:]:
                status = "ok" if tr.get("success") else "FAIL"
                lines.append(f"  [{status}] {tr.get('tool')}: {(tr.get('output') or tr.get('error', ''))[:100]}")

        verification = result.get("verification", {})
        if verification.get("format_check"):
            status_str = "PASSED" if verification["format_check"].get("passed") else "FAILED"
            lines.append(f"Format check: {status_str}")
        if verification.get("build_check"):
            status_str = "PASSED" if verification["build_check"].get("passed") else "FAILED"
            lines.append(f"Build check: {status_str}")
        if verification.get("test_results"):
            status_str = "PASSED" if verification["test_results"].get("passed") else "FAILED"
            lines.append(f"Tests: {status_str}")

        if result.get("success"):
            lines.append("Verification PASSED")
        else:
            lines.append("Verification FAILED")

        return "\n".join(lines)

    def stop(self) -> None:
        self._running = False
