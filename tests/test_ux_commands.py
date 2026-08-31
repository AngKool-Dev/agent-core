"""Tests for ARGUS UX commands."""

import pytest

from argus.ux.commands import CommandInfo, CommandPalette


class TestCommandInfo:
    """Tests for CommandInfo."""

    def test_create_command(self):
        cmd = CommandInfo("test", "Test command")
        assert cmd.name == "test"
        assert cmd.description == "Test command"
        assert cmd.category == "general"

    def test_matches_name(self):
        cmd = CommandInfo("test", "Test command")
        assert cmd.matches("test") is True
        assert cmd.matches("tes") is True

    def test_matches_description(self):
        cmd = CommandInfo("test", "A helpful command")
        assert cmd.matches("helpful") is True

    def test_matches_alias(self):
        cmd = CommandInfo("test", "Test command", aliases=["t", "tst"])
        assert cmd.matches("t") is True
        assert cmd.matches("tst") is True

    def test_no_match(self):
        cmd = CommandInfo("test", "Test command")
        assert cmd.matches("xyz") is False


class TestCommandPalette:
    """Tests for CommandPalette."""

    def test_default_commands(self):
        palette = CommandPalette()
        commands = palette.list_commands()
        assert len(commands) > 0

    def test_get_command(self):
        palette = CommandPalette()
        cmd = palette.get_command("help")
        assert cmd is not None
        assert cmd.name == "help"

    def test_get_nonexistent_command(self):
        palette = CommandPalette()
        assert palette.get_command("nonexistent") is None

    def test_search(self):
        palette = CommandPalette()
        results = palette.search("help")
        assert len(results) > 0

    def test_search_by_description(self):
        palette = CommandPalette()
        results = palette.search("provider")
        assert len(results) > 0

    def test_list_commands_by_category(self):
        palette = CommandPalette()
        commands = palette.list_commands(category="agent")
        assert len(commands) > 0
        for cmd in commands:
            assert cmd.category == "agent"

    def test_list_categories(self):
        palette = CommandPalette()
        categories = palette.list_categories()
        assert "general" in categories
        assert "agent" in categories

    def test_register_command(self):
        palette = CommandPalette()
        new_cmd = CommandInfo("newcmd", "A new command", "general")
        palette.register(new_cmd)
        assert palette.get_command("newcmd") is not None

    def test_format_help(self):
        palette = CommandPalette()
        help_text = palette.format_help()
        assert "Available Commands" in help_text
        assert "/help" in help_text
