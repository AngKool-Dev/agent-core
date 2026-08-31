"""Argus interactive REPL with polished terminal UX."""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
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


ANSI_SUPPORT = sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"

_SUCCESS = "#"
_WARN = "!"
_ERROR = "x"
_SPINNER = "|/-\\"

_GREEN = "#50fa7b"
_YELLOW = "#ffb86c"
_RED = "#ff5555"
_CYAN = "#5fb3f7"
_MAGENTA = "#ff79c6"
_DIM = "#666666"
_BOLD = "bold"


_COMMAND_GROUPS: List[Dict[str, Any]] = [
    {
        "name": "Agent",
        "commands": [
            ("agent", "agent", "Send a request to the agent (or just type naturally)"),
        ]
    },
    {
        "name": "Project",
        "commands": [
            ("project", "project", "Show project information"),
            ("clear", "clear", "Clear the screen"),
        ]
    },
    {
        "name": "Models",
        "commands": [
            ("model", "model", "Show or set model"),
            ("providers", "providers", "List model providers"),
            ("models", "models", "List available models"),
        ]
    },
    {
        "name": "Memory",
        "commands": [
            ("memory", "memory", "Memory operations (summary, search)"),
        ]
    },
    {
        "name": "Skills",
        "commands": [
            ("skills", "skills", "Skill operations (list, search, show)"),
        ]
    },
    {
        "name": "Session",
        "commands": [
            ("session", "session", "Session operations (new, list, load, save, delete)"),
        ]
    },
    {
        "name": "System",
        "commands": [
            ("config", "config", "Configuration (get, set, show)"),
            ("tools", "tools", "Tool operations (list, run)"),
            ("help", "help", "Show this help"),
            ("exit", "exit", "Exit Argus"),
            ("reality", "reality", "Production-reality qualification suite"),
        ]
    },
]

_ALL_COMMANDS = []
for _grp in _COMMAND_GROUPS:
    _ALL_COMMANDS.extend(_grp["commands"])
_COMMAND_NAMES = list(dict.fromkeys(c[1] for c in _ALL_COMMANDS))


def _get_command_names() -> List[str]:
    return list(_COMMAND_NAMES)


@dataclass
class _ToolDisplay:
    name: str
    description: str


def _ansi_code() -> str:
    return "\033[" if ANSI_SUPPORT else ""


def _supports_ansi() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            enable = ctypes.c_uint32(0)
            if kernel32.GetConsoleMode(kernel32.GetStdHandle(-11), ctypes.byref(enable)):
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), enable.value | 0x0001 | 0x0002 | 0x0004)
                return True
        except Exception:
            pass
        return os.environ.get("ANSICON") is not None or os.environ.get("WT_SESSION") is not None
    return True


_ANSI = _supports_ansi()


def _style_text(text: str, color: str, bold: bool = False) -> str:
    if not _ANSI:
        return text
    codes = []
    if bold:
        codes.append("1")
    colors = {
        _GREEN: "32", _YELLOW: "33", _RED: "31", _CYAN: "36",
        _MAGENTA: "35", _DIM: "2",
    }
    code = ";".join(filter(None, codes + [colors.get(color, "")]))
    return f"\033[{code}m{text}\033[0m"


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


_GATEWAY_HEALTH_CACHE: Dict[str, Any] = {}


def _check_gateway_available(config: ArgusConfig) -> bool:
    gateway_config = config.get("gateway", {})
    base_url = gateway_config.get("base_url", "")
    if not base_url:
        return False
    cache_key = base_url
    now = time.time()
    cached = _GATEWAY_HEALTH_CACHE.get(cache_key)
    if cached and now - cached.get("timestamp", 0) < 30:
        return cached.get("available", False)
    try:
        provider = GatewayModelProvider(
            base_url=base_url,
            api_key=gateway_config.get("api_key", ""),
        )
        health = provider.health()
        available = health.status == "ok" or health.anonymous_available
        _GATEWAY_HEALTH_CACHE[cache_key] = {"available": available, "timestamp": now}
        return available
    except Exception:
        _GATEWAY_HEALTH_CACHE[cache_key] = {"available": False, "timestamp": now}
        return False


class ArgusCompleter(Completer):
    """Completer for slash commands with descriptions."""

    def __init__(self, commands: List[str]):
        self._commands = sorted(commands)
        self._descriptions: Dict[str, str] = {}
        for cmd, name, desc in _ALL_COMMANDS:
            self._descriptions[name] = desc

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        text = document.text_before_cursor
        if text.startswith("/"):
            after_slash = text[1:]
            if " " in after_slash:
                return
            partial = after_slash
            for cmd in self._commands:
                if cmd.startswith(partial):
                    desc = self._descriptions.get(cmd, "")
                    display = f"/{cmd:<15} {desc}" if desc else f"/{cmd}"
                    yield Completion(
                        "/" + cmd,
                        start_position=-len(text),
                        display=display,
                        display_meta=desc,
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

        self._model = self._build_model()
        self.agent = ArgusAgent(
            project_path=self.project_path,
            config=self._build_agent_config(),
            status_callback=self._status_callback,
            model=self._model,
            skill_paths=self._build_skill_paths(),
            commit_approval_callback=self._commit_approval_prompt,
            tool_registry=self.tool_registry,
        )
        self.agent.discover_skills()

        self._history = InMemoryHistory()
        self._command_completer = ArgusCompleter(_get_command_names())
        self._session: Optional[PromptSession] = None
        self._use_prompt_toolkit = False

        self._status_lines: List[str] = []
        self._status_active = False
        self._spinner_char = 0
        self._spinner_thread: Optional[threading.Thread] = None

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
            model_config["base_url"] = self.config.get("model.base_url")
        try:
            return create_model_from_config(model_config)
        except Exception:
            return None

    def _determine_model_status(self) -> Dict[str, str]:
        gateway_config = self.config.get("gateway", {})
        has_gateway = bool(gateway_config and gateway_config.get("base_url"))
        has_byok = _has_byok_credentials(self.config, self._credentials)
        has_ollama = self.config.get("model.provider", "ollama") == "ollama"

        if has_byok:
            return {
                "mode": "BYOK",
                "provider": self.config.get("model.provider", "ollama"),
                "status": "Ready",
                "model": self.config.get("model.name", "auto"),
            }
        if has_gateway:
            available = _check_gateway_available(self.config)
            if available:
                return {
                    "mode": "Argus Free",
                    "provider": "gateway",
                    "status": "Ready",
                    "model": self.config.get("model.name", "auto"),
                }
            return {
                "mode": "Argus Free",
                "provider": "gateway",
                "status": "Gateway unreachable",
                "model": self.config.get("model.name", "auto"),
            }
        if has_ollama:
            return {
                "mode": "Local",
                "provider": "ollama",
                "status": "Not running",
                "model": self.config.get("model.name", "llama3"),
            }
        return {
            "mode": "Local fallback",
            "provider": "none",
            "status": "Not configured",
            "model": "auto",
        }

    def _permission_prompt(self, prompt: str, tool: str) -> bool:
        print()
        print(_style_text(prompt, _YELLOW))
        try:
            answer = input("Allow? [y/N]: ").strip().lower()
        except EOFError:
            return False
        return answer == "y"

    def _commit_approval_prompt(self, summary: str) -> bool:
        print()
        print(summary)
        try:
            answer = input("Commit these changes? [y/N]: ").strip().lower()
        except EOFError:
            return False
        return answer == "y"

    def _status_callback(self, message: str) -> None:
        if self._status_active:
            self._status_lines.append(message)

    def _start_spinner(self, message: str) -> None:
        if not _ANSI:
            self._status_active = True
            self._status_lines = [message]
            return
        self._status_active = True
        self._status_lines = [message]

        def spin():
            chars = _SPINNER
            i = 0
            while self._status_active:
                line = f"  {chars[i % len(chars)]} {self._status_lines[-1]}"
                sys.stdout.write("\r\033[K" + line)
                sys.stdout.flush()
                i += 1
                time.sleep(0.1)

        self._spinner_thread = threading.Thread(target=spin, daemon=True)
        self._spinner_thread.start()

    def _stop_spinner(self) -> None:
        if not self._status_active:
            return
        self._status_active = False
        if self._spinner_thread and self._spinner_thread.is_alive():
            self._spinner_thread.join(timeout=0.5)
        if _ANSI:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    def _print(self, text: str = "", color: str = "", bold: bool = False) -> None:
        if self._use_prompt_toolkit:
            style_color = {
                _GREEN: "ansigreen",
                _YELLOW: "ansiyellow",
                _RED: "ansired",
                _CYAN: "ansicyan",
                _MAGENTA: "ansimagenta",
                _DIM: "ansidefault",
            }
            sc = style_color.get(color, "")
            fmt = f'<style color="{color}" bold="{str(bold).lower()}">{text}</style>'
            print_formatted_text(HTML(fmt))
        else:
            styled = _style_text(text, color, bold) if color or bold else text
            print(styled)

    def _print_header(self) -> None:
        self._print()
        self._print("  ARGUS", _CYAN, bold=True)
        self._print("  AI Coding Agent", _DIM)
        self._print()

    def _print_startup_info(self) -> None:
        status = self._determine_model_status()
        self._print(f"  Project:  {self.project_path}", _CYAN)
        mode_display = self._get_mode_display(status)
        self._print(f"  Mode:      {mode_display}")
        self._print(f"  Model:     {status['model']}")
        self._print(f"  Status:    {status['status']}", self._status_color(status['status']))
        self._print()
        self._print("  Tip: Type a natural language request, or / for commands.")
        self._print()

    def _get_mode_display(self, status: Dict[str, str]) -> str:
        mode = status.get("mode", "")
        provider = status.get("provider", "")
        if mode == "Argus Free":
            return "Free (Argus Gateway)"
        if mode == "BYOK":
            return f"BYOK ({provider})"
        if mode == "Local":
            return f"Local ({provider})"
        return mode

    def _status_color(self, status: str) -> str:
        if status == "Ready":
            return _GREEN
        if "unreachable" in status.lower() or "not running" in status.lower() or "not configured" in status.lower():
            return _YELLOW
        return _DIM

    def _format_result(self, result: Dict[str, Any]) -> str:
        from argus.formatter import format_agent_result
        return format_agent_result(result, self.verbose)

    def _check_mark(self) -> str:
        return "v" if _ANSI else "ok"

    def _cross_mark(self) -> str:
        return "x" if _ANSI else "FAIL"

    def _display_agent_start(self, request: str) -> None:
        self._print()
        self._print(f"  {request}", _DIM)
        self._start_spinner("Working...")

    def _display_agent_result(self, result: Dict[str, Any]) -> None:
        self._stop_spinner()

        if self.verbose:
            from argus.formatter import format_agent_result
            output = format_agent_result(result, True)
            print()
            print(_style_text(output, _DIM))
            return

        tool_results = result.get("tool_results", [])
        verification = result.get("verification", {})
        success = result.get("success", False)

        print()
        if success:
            self._print(f"  [{self._check_mark()}] Completed", _GREEN)
        else:
            status = result.get("status", "FAILED")
            self._print(f"  [{self._cross_mark()}] {status}", _RED)

        if tool_results:
            self._print("  Tools used:")
            shown = set()
            for tr in tool_results:
                if tr.get("success"):
                    name = tr.get("tool", "")
                    if name not in shown:
                        self._print(f"    [{self._check_mark()}] {name}", _GREEN)
                        shown.add(name)

        if verification:
            checks = []
            if verification.get("format_check"):
                checks.append("format" if verification["format_check"].get("passed") else "format FAIL")
            if verification.get("build_check"):
                checks.append("build" if verification["build_check"].get("passed") else "build FAIL")
            if verification.get("test_results"):
                tr = verification["test_results"]
                if tr.get("passed"):
                    checks.append(f"Tests: {tr.get('total', '?')} passed")
                else:
                    checks.append("tests FAIL")
            if checks:
                self._print(f"  Verification: " + ", ".join(
                    _style_text(c, _GREEN if "FAIL" not in c else _RED) for c in checks
                ))

        final_response = result.get("final_response", "")
        if final_response and final_response.strip():
            self._print(f"  {final_response.strip()}")
        self._print()

    def _display_agent_error(self, error: str, error_type: str = "unexpected") -> None:
        self._stop_spinner()
        print()
        self._print(f"  [{self._cross_mark()}] Agent failed", _RED, bold=True)
        self._print()
        self._print(f"  Reason: {error}")
        self._print()
        self._print("  Try:")
        self._print("    /help", _CYAN)
        self._print("    /model", _CYAN)
        self._print("    /providers", _CYAN)
        self._print("    /config", _CYAN)
        self._print()

    def run(self) -> int:
        self._running = True
        self._use_prompt_toolkit = sys.stdin.isatty() and sys.stdout.isatty()

        if not self.session:
            default_name = f"session-{self.project_path.name}"
            self.session = self.session_manager.create(default_name, str(self.project_path))

        self._print_header()
        self._print_startup_info()

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
                        self._print(response)
                elif line.lower() in ("exit", "quit"):
                    raise SystemExit(0)
                else:
                    self._handle_message(line)

            except KeyboardInterrupt:
                self._stop_spinner()
                print()
                self._print(_style_text("  [CANCELLED]", _YELLOW))
                self.agent.cancel()
                continue
            except SystemExit:
                break
            except EOFError:
                print()
                break
            except Exception as e:
                self._stop_spinner()
                if self.verbose:
                    import traceback
                    traceback.print_exc()
                else:
                    self._print(_style_text(f"Error: {e}", _RED))

        self._stop_spinner()
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
            try:
                line = input("argus> ")
            except EOFError:
                return None
            except KeyboardInterrupt:
                return None
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

        self._display_agent_start(message)
        try:
            result = self.agent.execute(message)
            self._display_agent_result(result)
            self.session.add_message("assistant", result.get("final_response", ""), result=result)
        except KeyboardInterrupt:
            self._stop_spinner()
            self._print(_style_text("  [CANCELLED] Task was interrupted", _YELLOW))
            self.agent.cancel()
            self.session.add_message("assistant", "Task was cancelled", error="user_cancellation")
        except Exception as e:
            self._stop_spinner()
            self._display_agent_error(str(e))

    def stop(self) -> None:
        self._running = False
        self._status_active = False
