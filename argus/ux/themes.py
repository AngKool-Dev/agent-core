"""UX themes and styling."""

from typing import Dict, Optional


class UXTheme:
    """UX theme definition."""

    def __init__(self, name: str = "default"):
        self.name = name
        self._colors = self._get_default_colors()
        self._styles = self._get_default_styles()

    def _get_default_colors(self) -> Dict[str, str]:
        """Get default color scheme."""
        return {
            "primary": "#50fa7b",      # Green
            "secondary": "#8be9fd",    # Cyan
            "success": "#50fa7b",      # Green
            "warning": "#f1fa8c",      # Yellow
            "error": "#ff5555",        # Red
            "info": "#8be9fd",         # Cyan
            "debug": "#6272a4",        # Gray
            "text": "#f8f8f2",         # White
            "dim": "#6272a4",          # Gray
            "background": "#282a36",   # Dark
            "border": "#44475a",       # Gray
            "accent": "#bd93f9",       # Purple
        }

    def _get_default_styles(self) -> Dict[str, str]:
        """Get default styles."""
        return {
            "header": "bold",
            "success": "bold",
            "warning": "bold",
            "error": "bold",
            "info": "",
            "debug": "dim",
            "dim": "dim",
        }

    def get_color(self, name: str) -> str:
        """Get a color by name."""
        return self._colors.get(name, "#ffffff")

    def get_style(self, name: str) -> str:
        """Get a style by name."""
        return self._styles.get(name, "")

    def set_color(self, name: str, color: str) -> None:
        """Set a color."""
        self._colors[name] = color


class ThemeManager:
    """Manages UX themes."""

    def __init__(self):
        self._themes: Dict[str, UXTheme] = {}
        self._current_theme: str = "default"
        self._register_default_themes()

    def _register_default_themes(self) -> None:
        """Register default themes."""
        self._themes["default"] = UXTheme("default")
        self._themes["dark"] = UXTheme("dark")
        self._themes["light"] = self._create_light_theme()
        self._themes["minimal"] = self._create_minimal_theme()
        self._themes["accessible"] = self._create_accessible_theme()

    def _create_light_theme(self) -> UXTheme:
        """Create a light theme."""
        theme = UXTheme("light")
        theme._colors = {
            "primary": "#0066cc",
            "secondary": "#0088ff",
            "success": "#00aa00",
            "warning": "#cc8800",
            "error": "#cc0000",
            "info": "#0088ff",
            "debug": "#888888",
            "text": "#000000",
            "dim": "#888888",
            "background": "#ffffff",
            "border": "#cccccc",
            "accent": "#8800cc",
        }
        return theme

    def _create_minimal_theme(self) -> UXTheme:
        """Create a minimal theme."""
        theme = UXTheme("minimal")
        theme._colors = {
            "primary": "#ffffff",
            "secondary": "#aaaaaa",
            "success": "#ffffff",
            "warning": "#aaaaaa",
            "error": "#ff0000",
            "info": "#aaaaaa",
            "debug": "#666666",
            "text": "#ffffff",
            "dim": "#666666",
            "background": "#000000",
            "border": "#444444",
            "accent": "#ffffff",
        }
        return theme

    def _create_accessible_theme(self) -> UXTheme:
        """Create an accessible theme with high contrast."""
        theme = UXTheme("accessible")
        theme._colors = {
            "primary": "#00ff00",
            "secondary": "#00ffff",
            "success": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "info": "#00ffff",
            "debug": "#888888",
            "text": "#ffffff",
            "dim": "#888888",
            "background": "#000000",
            "border": "#ffffff",
            "accent": "#ff00ff",
        }
        return theme

    def get_theme(self, name: Optional[str] = None) -> UXTheme:
        """Get a theme by name."""
        name = name or self._current_theme
        return self._themes.get(name, self._themes["default"])

    def set_current_theme(self, name: str) -> bool:
        """Set the current theme."""
        if name in self._themes:
            self._current_theme = name
            return True
        return False

    def list_themes(self) -> list:
        """List available theme names."""
        return list(self._themes.keys())

    @property
    def current_theme(self) -> UXTheme:
        """Get the current theme."""
        return self.get_theme()
