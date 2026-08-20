"""Argus help command."""

from typing import List


def handle(repl) -> str:
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
