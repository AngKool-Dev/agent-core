"""Argus slash command handlers."""

import os
from typing import Any, Dict, List


class CommandContext:
    def __init__(self, repl: "ArgusREPL"):
        self.repl = repl

    def handle(self, command: str, args: List[str]) -> str:
        handler = getattr(self, f"cmd_{command}", None)
        if handler:
            return handler(args)
        return f"Unknown command: /{command}"

    def cmd_help(self, args: List[str]) -> str:
        commands = [
            ("help", "Show this help message"),
            ("exit, quit", "Exit the REPL"),
            ("clear", "Clear the screen"),
            ("session new <name>", "Create a new session"),
            ("session list", "List all sessions"),
            ("session load <name>", "Load a session"),
            ("session save", "Save current session"),
            ("session delete <name>", "Delete a session"),
            ("config get <key>", "Get a config value"),
            ("config set <key> <value>", "Set a config value"),
            ("config show", "Show all config"),
            ("tools list", "List available tools"),
            ("tools run <name> <args>", "Run a tool directly"),
            ("agent <request>", "Send a request to the agent"),
        ]
        lines = ["Available commands:"]
        for cmd, desc in commands:
            lines.append(f"  /{cmd:<25} {desc}")
        return "\n".join(lines)

    def cmd_exit(self, args: List[str]) -> str:
        raise SystemExit(0)

    def cmd_quit(self, args: List[str]) -> str:
        raise SystemExit(0)

    def cmd_clear(self, args: List[str]) -> str:
        os.system("cls" if os.name == "nt" else "clear")
        return ""

    def cmd_session(self, args: List[str]) -> str:
        if not args:
            return "Usage: /session <new|list|load|save|delete> [args]"

        sub = args[0]
        if sub == "new":
            name = args[1] if len(args) > 1 else None
            if not name:
                return "Usage: /session new <name>"
            session = self.repl.session_manager.create(name, str(self.repl.project_path))
            self.repl.session = session
            return f"Created session: {name}"

        elif sub == "list":
            sessions = self.repl.session_manager.list_sessions()
            return "\n".join(sessions) if sessions else "No sessions found"

        elif sub == "load":
            name = args[1] if len(args) > 1 else None
            if not name:
                return "Usage: /session load <name>"
            try:
                session = self.repl.session_manager.load(name)
                self.repl.session = session
                return f"Loaded session: {name} ({len(session.messages)} messages)"
            except FileNotFoundError:
                return f"Session not found: {name}"

        elif sub == "save":
            self.repl.session_manager.save_current()
            return "Session saved"

        elif sub == "delete":
            name = args[1] if len(args) > 1 else None
            if not name:
                return "Usage: /session delete <name>"
            self.repl.session_manager.delete(name)
            return f"Deleted session: {name}"

        return f"Unknown session command: {sub}"

    def cmd_config(self, args: List[str]) -> str:
        if not args:
            return "Usage: /config <get|set|show> [args]"

        sub = args[0]
        if sub == "show":
            import tomli_w

            return tomli_w.dumps(self.repl.config.raw)

        elif sub == "get":
            key = args[1] if len(args) > 1 else None
            if not key:
                return "Usage: /config get <key>"
            value = self.repl.config.get(key)
            return f"{key} = {value}"

        elif sub == "set":
            if len(args) < 3:
                return "Usage: /config set <key> <value>"
            key = args[1]
            value = args[2]
            self.repl.config.set(key, value)
            self.repl.config.save()
            return f"Set {key} = {value}"

        return f"Unknown config command: {sub}"

    def cmd_tools(self, args: List[str]) -> str:
        if not args:
            return "Usage: /tools <list|run> [args]"

        sub = args[0]
        if sub == "list":
            tools = self.repl.tool_registry.list_tools()
            lines = ["Available tools:"]
            for tool in tools:
                lines.append(f"  {tool['name']:<20} {tool['description']}")
            return "\n".join(lines)

        elif sub == "run":
            if len(args) < 2:
                return "Usage: /tools run <name> <args>"
            name = args[1]
            tool_args = " ".join(args[2:])
            import shlex

            try:
                parsed = shlex.split(tool_args)
                kwargs = {}
                for item in parsed:
                    if "=" in item:
                        k, v = item.split("=", 1)
                        kwargs[k] = v
                    else:
                        kwargs.setdefault("args", [])
                        kwargs["args"].append(item)
            except Exception as e:
                return f"Error parsing tool args: {e}"

            result = self.repl.tool_registry.execute(name, **kwargs)
            if result.success:
                return result.output
            return f"Error: {result.error}"

        return f"Unknown tools command: {sub}"

    def cmd_agent(self, args: List[str]) -> str:
        if not args:
            return "Usage: /agent <request>"

        request = " ".join(args)
        try:
            result = self.repl.agent.execute(request)
            status = self.repl.agent.status()

            lines = [
                f"Task: {result.get('task', {}).get('task_id', 'N/A')}",
                f"State: {status['status']}",
                f"Skills: {', '.join(status.get('skills', [])) or 'None'}",
                f"Tools used: {status.get('tools_used', 0)}",
                f"Success: {status.get('success', False)}",
            ]

            verification = result.get("verification", {})
            if verification.get("format_check"):
                lines.append(f"Format check: {'PASSED' if verification['format_check'].get('passed') else 'FAILED'}")
            if verification.get("build_check"):
                lines.append(f"Build check: {'PASSED' if verification['build_check'].get('passed') else 'FAILED'}")
            if verification.get("test_results"):
                lines.append(f"Tests: {'PASSED' if verification['test_results'].get('passed') else 'FAILED'}")

            return "\n".join(lines)
        except Exception as e:
            return f"Agent error: {e}"
