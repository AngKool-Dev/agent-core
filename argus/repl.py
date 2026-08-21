"""Argus interactive REPL with polished terminal UX."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from argus.agent import ArgusAgent, ArgusAgentConfig
from argus.commands import build_registry
from argus.config import ArgusConfig
from argus.model import create_model_from_config
from argus.model.credentials import CredentialManager
from argus.model.usage import UsageTracker
from argus.model.providers.gateway import GatewayModelProvider
from argus.permissions import PermissionConfig
from argus.session import SessionManager
from argus.tools import ToolRegistry

try:
    from argus.tools.bash import BashTool
    from argus.tools.file import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
    from argus.tools.search import GlobTool, GrepTool
    from argus.tools.git import GitAddTool, GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool, GitWorkflowTool
    from argus.tools.memory import MemoryAddTool, MemorySearchTool
    _TOOLS_AVAILABLE = True
except Exception:
    _TOOLS_AVAILABLE = False


_ARGUS_COLOR = "#5fb3f7"
_MUTED_COLOR = "#888888"
_SUCCESS_COLOR = "#50fa7b"
_WARN_COLOR = "#ffb86c"
_ERROR_COLOR = "#ff5555"
_STATUS_COLOR = "#5fb3f7"


def _get_model_display(config: ArgusConfig, credentials: CredentialManager) -> str:
    gateway_config = config.get("gateway", {})
    has_gateway = bool(gateway_config and gateway_config.get("base_url"))
    has_byok = _has_byok_credentials(config, credentials)
    has_ollama = config.get("model.provider", "ollama") == "ollama"

    if has_byok:
        provider = config.get("model.provider", "ollama")
        return f"BYOK | {provider}"
    if has_gateway:
        return "Argus Free"
    if has_ollama:
        return "Local | Ollama"
    return "Default"


def _has_byok_credentials(config: ArgusConfig, credentials: CredentialManager) -> bool:
    try:
        providers = config.get("providers", {})
        for name, pcfg in providers.items():
            key = pcfg.get("api_key", "")
            if key and credentials.get(name) is not None:
                return True
    except Exception:
        pass
    return False


class ArgusCompleter(Completer):
    """Completer for slash commands and natural language."""

    def __init__(self, commands: List[str]):
        self._commands = sorted(commands)

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            after_slash = text[1:]
            if " " in after_slash:
                return
            partial = after_slash
            for cmd in self._commands:
                if cmd.startswith(partial):
                    yield Completion(
                        "/" + cmd,
                        start_position=-len(text),
                    )


class ArgusREPL:
    def __init__(
        self,
        project_path: Optional[Path] = None,
        config: Optional[ArgusConfig] = None,
        verbose: bool = False,
    ):
        self.project_path = project_path or Path.cwd()
        self.config = config or ArgusConfig()
        self.verbose = verbose
        self._credentials = CredentialManager()
        self._usage = UsageTracker()

        permissions = PermissionConfig(
            read=self.config.get("permissions.read", "allow"),
            search=self.config.get("permissions.search", "allow"),
write=self.config.get("permissions.write", "allow"),
            bash=self.config.get("permissions.bash", "allow"),
            git=self.config.get("permissions.git", "allow"),
            browser=self.config.get("permissions.browser", "allow"),
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

        self.commands = build_registry()
        self._running = False

        self.agent = ArgusAgent(
            project_path=self.project_path,
            config=self._build_agent_config(),
            status_callback=self._status_callback,
            model=self._build_model(),
            skill_paths=self._build_skill_paths(),
            commit_approval_callback=self._commit_approval_prompt,
            tool_registry=self.tool_registry,
        )
        self.agent.discover_skills()

        self._history = InMemoryHistory()
        self._command_completer = ArgusCompleter(list(self.commands._commands.keys()))
        self._session: Optional[PromptSession] = None

    def _register_tools(self) -> None:
        if not _TOOLS_AVAILABLE:
            return
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
        self.tool_registry.register(GitWorkflowTool())
        self.tool_registry.register(MemoryAddTool())
        self.tool_registry.register(MemorySearchTool())

    def _build_agent_config(self) -> ArgusAgentConfig:
        return ArgusAgentConfig(
            max_iterations=self.config.get("agent.max_iterations", 10),
            max_tool_calls=self.config.get("agent.max_tools", 20),
            max_runtime_seconds=self.config.get("agent.timeout_seconds", 300),
            max_consecutive_failures=self.config.get("agent.max_consecutive_failures", 3),
            max_no_progress=self.config.get("agent.max_no_progress", 3),
            workspace_boundaries_enabled=self.config.get("agent.workspace_boundaries_enabled", True),
            model=self.config.get("model.name"),
            provider=self.config.get("model.provider"),
            enable_engineering_loop=self.config.get("agent.enable_engineering_loop", False),
            max_repair_attempts=self.config.get("agent.max_repair_attempts", 2),
            max_plan_revisions=self.config.get("agent.max_plan_revisions", 2),
        )

    def _build_skill_paths(self) -> List[Path]:
        paths = []
        builtin = Path(__file__).parent / "skills" / "builtin"
        if builtin.exists():
            paths.append(builtin)

        config_paths = self.config.get("skills.paths", [])
        for p in config_paths:
            paths.append(Path(p))

        return paths

    def _build_model(self):
        gateway_config = self.config.get("gateway", {})
        if gateway_config.get("base_url"):
            return GatewayModelProvider(
                base_url=gateway_config.get("base_url", ""),
                api_key=gateway_config.get("api_key", ""),
            )

        model_config = {
            "provider": self.config.get("model.provider", "ollama"),
            "name": self.config.get("model.name", "llama3"),
        }
        if self.config.get("model.api_key"):
            model_config["api_key"] = self.config.get("model.api_key")
        if self.config.get("model.base_url"):
            model_config["base_url"] = config.get("model.base_url")
        try:
            return create_model_from_config(model_config)
        except Exception:
            return None

    def _permission_prompt(self, prompt: str, tool: str) -> bool:
        print(f"\n[PERMISSION] {prompt}")
        answer = input("Allow? [y/N]: ").strip().lower()
        return answer == "y"

    def _commit_approval_prompt(self, summary: str) -> bool:
        print()
        print(summary)
        answer = input("Commit these changes? [y/N]: ").strip().lower()
        return answer == "y"

    def _status_callback(self, message: str) -> None:
        pass

    def _print_header_simple(self) -> None:
        lines = [
            "  A   R  U  S   --   AI Coding Agent",
            "",
        ]
        for line in lines:
            print(line)

    def _print_startup_info(self) -> None:
        mode_str = _get_model_display(self.config, self._credentials)
        model_name = self.config.get("model.name", "auto")
        print()
        print(f"  Project   {self.project_path}")
        print(f"  Mode      {mode_str}")
        print(f"  Model     {model_name}")
        print()
        print("  Type /help for commands, or just ask anything.")
        print()

    def _format_result(self, result: Dict[str, Any]) -> str:
        from argus.formatter import format_agent_result
        return format_agent_result(result, self.verbose)

    def run(self) -> int:
        self._running = True

        if not self.session:
            default_name = f"session-{self.project_path.name}"
            self.session = self.session_manager.create(default_name, str(self.project_path))

        self._print_header_simple()
        self._print_startup_info()

        self._use_prompt_toolkit = sys.stdin.isatty() and sys.stdout.isatty()

        if self._use_prompt_toolkit:
            try:
                self._session = PromptSession(
                    completer=self._command_completer,
                    history=self._history,
                    complete_while_typing=True,
                    enable_history_search=True,
                    complete_event_wait_time=0,
                )
            except Exception:
                self._use_prompt_toolkit = False

        while self._running:
            try:
                line = self._read_input()
                if line is None:
                    break
                if not line:
                    continue

                if line.startswith("/"):
                    response = self._handle_command(line)
                    if response:
                        if self._use_prompt_toolkit:
                            print_formatted_text(HTML('<style color="' + _SUCCESS_COLOR + '">' + response + '</>'))
                        else:
                            print(response)
                else:
                    self._handle_message(line)

            except KeyboardInterrupt:
                if self._use_prompt_toolkit:
                    print()
                print(_color_text("[CANCELLED]", _WARN_COLOR))
                self.agent.cancel()
                continue
            except SystemExit:
                break
            except EOFError:
                print()
                break
            except Exception as e:
                if self.verbose:
                    import traceback
                    traceback.print_exc()
                else:
                    print(_color_text("Error: " + str(e), _ERROR_COLOR))

        self.session_manager.save_current()
        return 0

    def _read_input(self) -> Optional[str]:
        if self._use_prompt_toolkit and self._session:
            line = self._session.prompt(
                "│ ",
                style=Style.from_dict({
                    "prompt": "ansifg:#5fb3f7",
                    "continuation": "ansifg:#5fb3f7",
                }),
                prompt_default="Ask Argus anything...",
            )
        else:
            line = input("argus> ")
        return line.strip() if line else ""

    def _handle_command(self, line: str) -> str:
        parts = line[1:].split()
        if not parts:
            return ""
        command = parts[0]
        args = parts[1:]
        return self.commands.handle(command, self, args)

    def _handle_message(self, message: str) -> None:
        self.session.add_message("user", message)

        if self._use_prompt_toolkit:
            print_formatted_text(HTML('<style color="' + _STATUS_COLOR + '">Argus:</>'))
        else:
            print("Argus:")
        try:
            result = self.agent.execute(message)
            response = self._format_result(result)
            if response:
                print("  " + response)
            self.session.add_message("assistant", response, result=result)
        except KeyboardInterrupt:
            if self._use_prompt_toolkit:
                print_formatted_text(HTML('<style color="' + _WARN_COLOR + '">  [CANCELLED] Task was interrupted</>'))
            else:
                print("  [CANCELLED] Task was interrupted")
            self.agent.cancel()
            self.session.add_message("assistant", "Task was cancelled", error="user_cancellation")
        except Exception as e:
            if self._use_prompt_toolkit:
                print_formatted_text(HTML('<style color="' + _ERROR_COLOR + '">  ' + str(e) + '</>'))
            else:
                print("  " + str(e))
            self.session.add_message("assistant", str(e), error=str(e))

    def stop(self) -> None:
        self._running = False
