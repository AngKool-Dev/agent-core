//! Renderer — handles terminal rendering for ARGUS.
//!
//! Uses crossterm for terminal I/O and ratatui for drawing.
//! Manages terminal setup, teardown, and the main render loop.

use crate::argus::Section;
use crate::argus::focus::FocusManager;
use crate::argus::state::AppState;
use crate::argus::ui;
use crossterm::ExecutableCommand;
use crossterm::event::{self, Event as CEvent};
use crossterm::terminal::{self, EnterAlternateScreen, LeaveAlternateScreen};
use ratatui::backend::CrosstermBackend;
use ratatui::prelude::*;
use ratatui::widgets::Paragraph;
use std::io;
use std::time::Duration;

/// The renderer handles terminal I/O and the render loop.
pub struct Renderer {
    terminal: Terminal<CrosstermBackend<io::Stdout>>,
}

impl Renderer {
    /// Initialize the terminal for ARGUS
    pub fn init() -> io::Result<Self> {
        let mut stdout = io::stdout();
        stdout.execute(EnterAlternateScreen)?;
        terminal::enable_raw_mode()?;
        let backend = CrosstermBackend::new(stdout);
        let terminal = Terminal::new(backend)?;
        Ok(Self { terminal })
    }

    /// Clean up terminal on exit
    pub fn deinit(&mut self) -> io::Result<()> {
        let mut stdout = io::stdout();
        stdout.execute(LeaveAlternateScreen)?;
        terminal::disable_raw_mode()?;
        Ok(())
    }

    /// Get the terminal size as Rect
    pub fn size(&self) -> Rect {
        let size = self
            .terminal
            .size()
            .unwrap_or(ratatui::layout::Size::new(80, 24));
        Rect::new(0, 0, size.width, size.height)
    }

    /// Block on a crossterm event with timeout
    pub fn read_event(&mut self, timeout: Duration) -> Option<CEvent> {
        if event::poll(timeout).unwrap_or(false) {
            event::read().ok()
        } else {
            None
        }
    }

    /// Render the full ARGUS UI
    pub fn render(&mut self, state: &AppState, focus: &FocusManager) -> io::Result<()> {
        // Resolve the active palette when the settings value changes (the
        // apply() cache makes this a no-op most frames).
        crate::argus::theme::apply(&crate::argus::backend::BackendBridge::get_settings().theme);
        self.terminal.draw(|f| Self::draw_app(f, state, focus))?;
        Ok(())
    }

    /// The main rendering function — draws all UI sections
    fn draw_app(f: &mut Frame, state: &AppState, focus: &FocusManager) {
        // Rebuild the mouse hit-test map for this frame.
        if let Ok(mut map) = ui::MOUSE_TARGETS.lock() {
            map.clear();
        }

        let area = f.area();
        f.render_widget(
            Paragraph::new("").style(Style::default().bg(crate::argus::theme::current().bg)),
            area,
        );

        // Layout: Header (5 lines), Navbar (3 lines), Main content, Command/Loading (3 lines), Status (1 line)
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(5), // Header
                Constraint::Length(3), // Navbar
                Constraint::Min(0),    // Main content
                Constraint::Length(3), // Command/Loading
                Constraint::Length(1), // Status bar
            ])
            .split(area);

        // Header
        ui::draw_header(f, chunks[0], state, focus);

        // Navbar (tabs)
        ui::draw_navbar(f, chunks[1], state, focus);

        // Main content (based on current section)
        match state.current_section {
            Section::Home => ui::draw_home(f, chunks[2], state, focus),
            Section::Discover => ui::draw_discover(f, chunks[2], state, focus),
            Section::Instances => ui::draw_instance_list(f, chunks[2], state, focus),
            Section::Mods => ui::draw_mods(f, chunks[2], state, focus),
            Section::Worlds => ui::draw_worlds(f, chunks[2], state, focus),
            Section::Logs => ui::draw_logs(f, chunks[2], state, focus),
            Section::Settings => ui::draw_settings(f, chunks[2], state, focus),
        }

        // Command prompt or loading
        if state.command_prompt_active {
            ui::draw_command_prompt(f, chunks[3], state);
        } else if state.loading {
            ui::draw_loading_bar(f, chunks[3], state);
        }

        // Status bar
        ui::draw_status_bar(f, chunks[4], state);

        // Help overlay on top of everything
        if state.help_overlay {
            ui::draw_help_overlay(f, area, state);
        }

        // Loader picker overlays the help overlay when open
        if state.loader_selector_open {
            ui::draw_loader_selector(f, area, state);
        }

        // Version picker (create flow step 2)
        if state.version_selector_open {
            ui::draw_version_selector(f, area, state);
        }

        // Per-mod install version chooser on top of results
        if state.pending_install.is_some() {
            ui::draw_install_version_overlay(f, area, state);
        }

        // Account picker / new-account input on top of everything
        if state.account_selector_open {
            ui::draw_account_selector(f, area, state);
        }
        if state.account_input_mode {
            ui::draw_account_input(f, area, state);
        }
    }
}
