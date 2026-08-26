//! ARGUS — Terminal-native Minecraft runtime control UI for EraLauncher.
//!
//! This module provides a terminal-based UI that integrates with the existing
//! EraLauncher backend. It uses crossterm for input and ratatui for rendering.

pub mod app;
pub mod backend;
pub mod command;
pub mod events;
pub mod focus;
pub mod render;
pub mod state;
pub mod theme;
pub mod ui;
pub mod update;

pub use app::ArgusApp;
pub use command::CommandManager;
pub use events::ArgusEvent;
pub use focus::{FocusManager, FocusTarget};
pub use render::Renderer;
pub use state::{AppState, RuntimeState, Section};
