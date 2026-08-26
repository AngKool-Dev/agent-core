//! Theme — runtime-switchable color palettes for ARGUS.
//!
//! The settings value `theme` ("dark" | "light" | "system") is resolved to a
//! [`Theme`] palette and applied globally before each frame. Every drawing
//! function reads the active palette via [`current`] so switching themes
//! takes effect immediately (previously colors were hardcoded constants and
//! the setting did nothing visually).

use ratatui::prelude::Color;
use std::sync::RwLock;

/// A complete color palette for the terminal UI.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Theme {
    pub name: &'static str,
    pub bg: Color,
    pub bg_dark: Color,
    pub panel: Color,
    pub border: Color,
    pub border_focus: Color,
    pub accent: Color,
    pub accent_dim: Color,
    pub text: Color,
    pub text_dim: Color,
    pub text_muted: Color,
    pub success: Color,
    pub warning: Color,
    pub error: Color,
    pub info: Color,
    pub focus: Color,
    pub fabric: Color,
    pub forge: Color,
    pub vanilla: Color,
}

impl Theme {
    /// SKlauncher-inspired dark palette (original look).
    pub const DARK: Theme = Theme {
        name: "dark",
        bg: Color::Rgb(15, 15, 23),
        bg_dark: Color::Rgb(10, 10, 18),
        panel: Color::Rgb(25, 25, 35),
        border: Color::Rgb(60, 60, 80),
        border_focus: Color::Rgb(80, 200, 120),
        accent: Color::Rgb(80, 200, 120),
        accent_dim: Color::Rgb(60, 160, 100),
        text: Color::Rgb(220, 220, 220),
        text_dim: Color::Rgb(120, 120, 140),
        text_muted: Color::Rgb(90, 90, 110),
        success: Color::Rgb(80, 200, 120),
        warning: Color::Rgb(255, 200, 80),
        error: Color::Rgb(240, 80, 80),
        info: Color::Rgb(100, 180, 240),
        focus: Color::Rgb(100, 180, 255),
        fabric: Color::Rgb(100, 120, 255),
        forge: Color::Rgb(240, 120, 60),
        vanilla: Color::Rgb(200, 200, 200),
    };

    /// Light palette — same structure, readable on bright terminals.
    pub const LIGHT: Theme = Theme {
        name: "light",
        bg: Color::Rgb(243, 243, 246),
        bg_dark: Color::Rgb(228, 228, 233),
        panel: Color::Rgb(255, 255, 255),
        border: Color::Rgb(185, 185, 198),
        border_focus: Color::Rgb(20, 140, 90),
        accent: Color::Rgb(16, 130, 84),
        accent_dim: Color::Rgb(60, 160, 100),
        text: Color::Rgb(30, 30, 40),
        text_dim: Color::Rgb(95, 95, 110),
        text_muted: Color::Rgb(130, 130, 145),
        success: Color::Rgb(16, 130, 84),
        warning: Color::Rgb(170, 115, 0),
        error: Color::Rgb(200, 40, 40),
        info: Color::Rgb(20, 100, 200),
        focus: Color::Rgb(20, 90, 190),
        fabric: Color::Rgb(70, 90, 210),
        forge: Color::Rgb(200, 90, 30),
        vanilla: Color::Rgb(80, 80, 90),
    };

    /// Resolve a settings string ("dark" | "light" | "system") to a palette.
    pub fn resolve(name: &str) -> Theme {
        match name.to_lowercase().as_str() {
            "light" => Theme::LIGHT,
            "system" => detect_system_theme(),
            _ => Theme::DARK,
        }
    }
}

/// Detect the OS-wide light/dark preference. Windows reads the registry;
/// other platforms currently default to dark.
fn detect_system_theme() -> Theme {
    if cfg!(windows) {
        let output = std::process::Command::new("reg")
            .args([
                "query",
                r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                "/v",
                "AppsUseLightTheme",
            ])
            .output();
        if let Ok(out) = output {
            let text = String::from_utf8_lossy(&out.stdout);
            // The value line ends with something like "REG_DWORD 0x1".
            for token in text.split_whitespace() {
                if token == "0x1" {
                    return Theme::LIGHT;
                }
                if token == "0x0" {
                    return Theme::DARK;
                }
            }
        }
    }
    Theme::DARK
}

static CURRENT: RwLock<Theme> = RwLock::new(Theme::DARK);

/// Cache of the last applied settings string so `apply` can skip redundant
/// resolution. Without this, the "system" theme spawned a `reg query`
/// subprocess on EVERY rendered frame.
static APPLIED_NAME: RwLock<Option<String>> = RwLock::new(None);

/// Apply a theme by settings name. Safe to call every frame — repeated
/// calls with the same name are no-ops.
pub fn apply(name: &str) {
    {
        let cached = APPLIED_NAME.read().ok();
        if let Some(guard) = cached {
            if guard.as_deref() == Some(name) {
                return;
            }
        }
    }
    let theme = Theme::resolve(name);
    if let Ok(mut guard) = CURRENT.write() {
        *guard = theme;
    }
    if let Ok(mut guard) = APPLIED_NAME.write() {
        *guard = Some(name.to_string());
    }
}

/// Get a copy of the currently active palette.
pub fn current() -> Theme {
    CURRENT.read().map(|t| *t).unwrap_or(Theme::DARK)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolve_dark() {
        assert_eq!(Theme::resolve("dark"), Theme::DARK);
        assert_eq!(Theme::resolve("unknown"), Theme::DARK);
        assert_eq!(Theme::resolve(""), Theme::DARK);
    }

    #[test]
    fn test_resolve_light() {
        assert_eq!(Theme::resolve("light"), Theme::LIGHT);
        assert_eq!(Theme::resolve("LIGHT"), Theme::LIGHT);
    }

    #[test]
    fn test_resolve_system_returns_valid_palette() {
        let t = Theme::resolve("system");
        assert!(t == Theme::DARK || t == Theme::LIGHT);
    }

    #[test]
    fn test_palettes_differ() {
        assert_ne!(Theme::DARK.bg, Theme::LIGHT.bg);
        assert_ne!(Theme::DARK.text, Theme::LIGHT.text);
    }

    #[test]
    fn test_apply_and_current_roundtrip() {
        apply("light");
        assert_eq!(current().name, "light");
        apply("dark");
        assert_eq!(current().name, "dark");
    }
}
