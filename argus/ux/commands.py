"""UX command palette and command handling."""

from typing import Dict, List, Optional

from argus.ux.models import PanelView


class CommandInfo:
    """Information about a command."""

    def __init__(
        self,
        name: str,
        description: str,
        category: str = "general",
        aliases: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.category = category
        self.aliases = aliases or []

    def matches(self, query: str) -> bool:
        """Check if the command matches a query."""
        query = query.lower()
        if query in self.name.lower():
            return True
        if query in self.description.lower():
            return True
        for alias in self.aliases:
            if query in alias.lower():
                return True
        return False


class CommandPalette:
    """Discoverable command palette."""

    def __init__(self):
        self._commands: Dict[str, CommandInfo] = {}
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        """Register default commands."""
        commands = [
            CommandInfo("help", "Show available commands", "general"),
            CommandInfo("status", "Show current status", "general"),
            CommandInfo("plan", "Show execution plan", "agent"),
            CommandInfo("pause", "Pause current execution", "agent"),
            CommandInfo("resume", "Resume paused execution", "agent"),
            CommandInfo("cancel", "Cancel current execution", "agent"),
            CommandInfo("providers", "Show provider status", "providers"),
            CommandInfo("models", "Show available models", "providers"),
            CommandInfo("capabilities", "Show capabilities", "providers"),
            CommandInfo("security", "Show security status", "security"),
            CommandInfo("audit", "Show audit trail", "security"),
            CommandInfo("performance", "Show performance metrics", "performance"),
            CommandInfo("verification", "Show verification status", "quality"),
            CommandInfo("recovery", "Show recovery status", "quality"),
            CommandInfo("review", "Show review status", "quality"),
            CommandInfo("trace", "Show execution trace", "debug"),
            CommandInfo("replay", "Replay a previous run", "debug"),
            CommandInfo("doctor", "Run diagnostics", "system"),
            CommandInfo("session", "Manage sessions", "system"),
            CommandInfo("config", "Manage configuration", "system"),
            CommandInfo("exit", "Exit ARGUS", "system"),
        ]
        for cmd in commands:
            self._commands[cmd.name] = cmd

    def register(self, command: CommandInfo) -> None:
        """Register a command."""
        self._commands[command.name] = command

    def get_command(self, name: str) -> Optional[CommandInfo]:
        """Get a command by name."""
        return self._commands.get(name)

    def search(self, query: str) -> List[CommandInfo]:
        """Search for commands matching a query."""
        return [cmd for cmd in self._commands.values() if cmd.matches(query)]

    def list_commands(self, category: Optional[str] = None) -> List[CommandInfo]:
        """List commands, optionally filtered by category."""
        commands = list(self._commands.values())
        if category:
            commands = [c for c in commands if c.category == category]
        return commands

    def list_categories(self) -> List[str]:
        """List all categories."""
        return list(set(c.category for c in self._commands.values()))

    def format_help(self) -> str:
        """Format command help."""
        categories = {}
        for cmd in self._commands.values():
            if cmd.category not in categories:
                categories[cmd.category] = []
            categories[cmd.category].append(cmd)

        lines = ["Available Commands:", ""]
        for category, commands in sorted(categories.items()):
            lines.append(f"  {category.upper()}:")
            for cmd in sorted(commands, key=lambda c: c.name):
                lines.append(f"    /{cmd.name:<15} {cmd.description}")
            lines.append("")

        return "\n".join(lines)
