"""Tests for ARGUS UX themes."""

import pytest

from argus.ux.themes import ThemeManager, UXTheme


class TestUXTheme:
    """Tests for UXTheme."""

    def test_default_theme(self):
        theme = UXTheme("default")
        assert theme.name == "default"
        assert theme.get_color("primary") == "#50fa7b"
        assert theme.get_color("error") == "#ff5555"

    def test_get_color(self):
        theme = UXTheme()
        assert theme.get_color("primary") == "#50fa7b"
        assert theme.get_color("nonexistent") == "#ffffff"  # Default

    def test_set_color(self):
        theme = UXTheme()
        theme.set_color("primary", "#000000")
        assert theme.get_color("primary") == "#000000"

    def test_get_style(self):
        theme = UXTheme()
        assert theme.get_style("header") == "bold"
        assert theme.get_style("nonexistent") == ""  # Default


class TestThemeManager:
    """Tests for ThemeManager."""

    def test_default_theme(self):
        manager = ThemeManager()
        theme = manager.get_theme("default")
        assert theme.name == "default"

    def test_dark_theme(self):
        manager = ThemeManager()
        theme = manager.get_theme("dark")
        assert theme.name == "dark"

    def test_light_theme(self):
        manager = ThemeManager()
        theme = manager.get_theme("light")
        assert theme.name == "light"

    def test_minimal_theme(self):
        manager = ThemeManager()
        theme = manager.get_theme("minimal")
        assert theme.name == "minimal"

    def test_accessible_theme(self):
        manager = ThemeManager()
        theme = manager.get_theme("accessible")
        assert theme.name == "accessible"

    def test_get_nonexistent_theme(self):
        manager = ThemeManager()
        theme = manager.get_theme("nonexistent")
        assert theme.name == "default"  # Falls back to default

    def test_set_current_theme(self):
        manager = ThemeManager()
        assert manager.set_current_theme("dark") is True
        assert manager.current_theme.name == "dark"

    def test_set_invalid_theme(self):
        manager = ThemeManager()
        assert manager.set_current_theme("nonexistent") is False

    def test_list_themes(self):
        manager = ThemeManager()
        themes = manager.list_themes()
        assert "default" in themes
        assert "dark" in themes
        assert "light" in themes
        assert "minimal" in themes
        assert "accessible" in themes
