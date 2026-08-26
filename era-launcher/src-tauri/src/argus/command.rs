//! CommandManager — handles terminal command parsing and execution.
//!
//! Commands trigger the same backend actions as the UI buttons.
//! This ensures command/UI action equivalence.

use crate::argus::Section;
use crate::argus::backend::BackendBridge;
use crate::argus::backend::RuntimeTracker;
use crate::argus::state::{AppState, LogLevel, RuntimeState};

#[derive(Debug)]
pub enum CommandResult {
    /// Command executed successfully, with optional message
    Success(Option<String>),
    /// Command failed with an error message
    Error(String),
    /// Command produced output (multi-line)
    Output(String),
    /// Navigate to a section
    Navigate(Section),
    /// Show help
    Help,
    /// Quit the application
    Quit,
    /// No result (for commands that don't produce output)
    None,
}

/// Manages command parsing and execution
pub struct CommandManager;

impl CommandManager {
    /// Parse and execute a command string
    pub fn execute(
        input: &str,
        state: &mut AppState,
        tracker: &mut RuntimeTracker,
    ) -> CommandResult {
        let input = input.trim();
        if input.is_empty() {
            return CommandResult::None;
        }

        let parts: Vec<&str> = input.splitn(2, ' ').collect();
        let cmd = parts[0].to_lowercase();
        let args = if parts.len() > 1 {
            Some(parts[1])
        } else {
            None
        };

        match cmd.as_str() {
            "launch" => Self::cmd_launch(state, tracker, args),
            "stop" => Self::cmd_stop(state, tracker),
            "status" => Self::cmd_status(state, tracker),
            "instances" => CommandResult::Navigate(Section::Instances),
            "discover" => CommandResult::Navigate(Section::Discover),
            "mods" => CommandResult::Navigate(Section::Mods),
            "modpacks" => CommandResult::Navigate(Section::Discover),
            "shaders" => CommandResult::Navigate(Section::Discover),
            "resourcepacks" | "resource_packs" => CommandResult::Navigate(Section::Discover),
            "worlds" => CommandResult::Navigate(Section::Worlds),
            "logs" => CommandResult::Navigate(Section::Logs),
            "settings" => Self::cmd_settings(state, args),
            "home" => CommandResult::Navigate(Section::Home),
            "help" => CommandResult::Help,
            "clear" => CommandResult::Success(Some("clear".to_string())),
            "exit" | "quit" => CommandResult::Quit,
            "create" => Self::cmd_create(state, args),
            "delete" => Self::cmd_delete(state, args),
            "edit" => Self::cmd_edit(state, args),
            "account" | "accounts" => Self::cmd_account(state, args),
            "java" => Self::cmd_java(state),
            "versions" => Self::cmd_versions(state),
            "search" => Self::cmd_search(state, args),
            "update" => Self::cmd_update(state),
            _ => CommandResult::Error(format!(
                "Unknown command: '{}'. Type 'help' for available commands.",
                cmd
            )),
        }
    }

    fn cmd_launch(
        state: &mut AppState,
        tracker: &mut RuntimeTracker,
        args: Option<&str>,
    ) -> CommandResult {
        let instance_name = args.unwrap_or("selected");
        let instance = if let Some(name) = args {
            // Find by name
            state
                .instances
                .iter()
                .find(|i| i.name == name || i.id == name)
                .cloned()
        } else {
            // Use selected or first
            state
                .selected_instance
                .clone()
                .or_else(|| state.instances.first().cloned())
        };

        match instance {
            Some(inst) => {
                state.runtime_state = RuntimeState::Starting;
                state.set_loading(true, Some("Preparing launch...".to_string()));
                state.log(
                    LogLevel::Info,
                    "CMD",
                    &format!("Launching instance: {}", inst.name),
                );

                // Background pipeline: progress streams via tracker events.
                BackendBridge::spawn_launch(&inst, state, tracker);
                CommandResult::Success(Some(format!(
                    "Launching '{}' in background — watch the progress bar",
                    inst.name
                )))
            }
            None => CommandResult::Error(format!(
                "No instance '{}' found. Use 'instances' to see available instances.",
                instance_name
            )),
        }
    }

    fn cmd_stop(state: &mut AppState, tracker: &mut RuntimeTracker) -> CommandResult {
        match state.runtime_state {
            RuntimeState::Running => {
                state.runtime_state = RuntimeState::Stopping;
                state.log(LogLevel::Info, "CMD", "Stopping Minecraft...");
                // Attempt to terminate the process
                let stopped = BackendBridge::stop_instance(state, tracker);
                if stopped {
                    state.runtime_state = RuntimeState::Stopped;
                    CommandResult::Success(Some("Minecraft process stopped.".to_string()))
                } else {
                    state.runtime_state = RuntimeState::Error("Failed to stop process".to_string());
                    CommandResult::Error("Failed to stop Minecraft process.".to_string())
                }
            }
            RuntimeState::Stopped => CommandResult::Error("Minecraft is not running.".to_string()),
            RuntimeState::Starting | RuntimeState::Stopping => {
                CommandResult::Error("Minecraft is still starting/stopping.".to_string())
            }
            RuntimeState::Error(ref e) => {
                CommandResult::Error(format!("Minecraft is in error state: {}", e))
            }
        }
    }

    fn cmd_status(state: &AppState, tracker: &RuntimeTracker) -> CommandResult {
        let status = &state.runtime_state;
        let instance = state
            .selected_instance
            .as_ref()
            .map(|i| i.name.as_str())
            .unwrap_or("None");
        let java_version = state
            .java_installations
            .first()
            .and_then(|j| j.version.as_ref())
            .map(|v| v.major)
            .unwrap_or(0);

        let pid_str = tracker
            .pid()
            .map(|p| p.to_string())
            .unwrap_or("N/A".to_string());

        let output = format!(
            "ARGUS Runtime Status\n\
            ─────────────────────────\n\
            Runtime: {} {}\n\
            Instance: {}\n\
            PID: {}\n\
            Minecraft: {}\n\
            Loader: {}\n\
            Java: Java {}\n\
            RAM: {} GB",
            status.status_indicator(),
            status.label(),
            instance,
            pid_str,
            state
                .selected_instance
                .as_ref()
                .map(|i| i.game_version.as_str())
                .unwrap_or("N/A"),
            state
                .selected_instance
                .as_ref()
                .map(|i| i.loader.as_str())
                .unwrap_or("N/A"),
            java_version,
            state
                .selected_instance
                .as_ref()
                .map(|i| i.memory / 1024)
                .unwrap_or(0),
        );
        CommandResult::Output(output)
    }

    fn cmd_create(state: &mut AppState, args: Option<&str>) -> CommandResult {
        // Syntax: create [vanilla|fabric|quilt] [name...]
        let mut loader: Option<String> = None;
        let mut name: Option<String> = None;
        if let Some(raw) = args {
            let mut parts = raw.split_whitespace();
            if let Some(first) = parts.next() {
                let known = ["vanilla", "fabric", "quilt", "forge"];
                if known.contains(&first.to_lowercase().as_str()) {
                    loader = Some(first.to_lowercase());
                    let rest: Vec<&str> = parts.collect();
                    if !rest.is_empty() {
                        name = Some(rest.join(" "));
                    }
                } else {
                    name = Some(raw.to_string());
                }
            }
        }

        let instance = if let Some(l) = loader {
            match BackendBridge::quick_create_instance_with_loader(state, &l) {
                Ok(i) => i,
                Err(e) => return CommandResult::Error(e),
            }
        } else {
            BackendBridge::quick_create_instance(state)
        };
        state.selected_instance = Some(instance.clone());

        if let Some(custom_name) = name {
            let renamed = crate::instances::InstanceConfig {
                name: custom_name.to_string(),
                ..instance.clone()
            };
            if BackendBridge::update_instance(renamed.clone()) {
                if let Some(sel) = state.selected_instance.as_mut() {
                    *sel = renamed.clone();
                }
                return CommandResult::Success(Some(format!(
                    "Created and renamed instance '{}' ({})",
                    renamed.name, renamed.loader
                )));
            }
            // Do NOT fall through to the generic success message — that
            // would report the auto-generated name as if the rename worked.
            return CommandResult::Error(format!(
                "Created instance '{}' but failed to rename it to '{}'",
                instance.name, custom_name
            ));
        }
        CommandResult::Success(Some(format!(
            "Created instance '{}' ({}, v{}, persisted)",
            instance.name, instance.loader, instance.game_version
        )))
    }

    fn cmd_delete(state: &mut AppState, args: Option<&str>) -> CommandResult {
        if let Some(id) = args {
            if let Some(idx) = state
                .instances
                .iter()
                .position(|i| i.id == id || i.name == id)
            {
                let target = state.instances[idx].clone();
                // Persist deletion via the real backend (manager + config).
                if BackendBridge::delete_instance(&target.id) {
                    state.instances.remove(idx);
                    if state
                        .selected_instance
                        .as_ref()
                        .map(|s| s.id == target.id)
                        .unwrap_or(false)
                    {
                        state.selected_instance = None;
                    }
                    CommandResult::Success(Some(format!(
                        "Deleted instance '{}' (persisted)",
                        target.name
                    )))
                } else {
                    CommandResult::Error(format!("Failed to delete instance '{}'.", target.name))
                }
            } else {
                CommandResult::Error(format!("Instance '{}' not found.", id))
            }
        } else {
            CommandResult::Error("Usage: delete <instance-id-or-name>".to_string())
        }
    }

    fn cmd_edit(state: &mut AppState, args: Option<&str>) -> CommandResult {
        let _ = args;
        if state.selected_instance.is_some() {
            CommandResult::Success(Some("Opening instance editor via backend...".to_string()))
        } else {
            CommandResult::Error("No instance selected.".to_string())
        }
    }

    /// Handle the `settings` command — show current settings or edit a specific key.
    /// Manage offline accounts: list / add <name> / use <name> / remove <name>
    fn cmd_account(state: &mut AppState, args: Option<&str>) -> CommandResult {
        let (sub, rest) = match args {
            Some(a) => {
                let mut it = a.splitn(2, char::is_whitespace);
                (
                    it.next().unwrap_or("list").to_lowercase(),
                    it.next().map(|s| s.trim().to_string()),
                )
            }
            None => ("list".to_string(), None),
        };

        match sub.as_str() {
            "list" => {
                let accounts = BackendBridge::list_accounts();
                if accounts.is_empty() {
                    return CommandResult::Output(
                        "No offline accounts yet.\nAdd one: account add <username>\n\
                         Until then launches use the default name 'Steve'."
                            .to_string(),
                    );
                }
                let active = BackendBridge::active_account().map(|a| a.id);
                let mut out = String::from("Offline accounts:\n");
                for a in &accounts {
                    let marker = if Some(&a.id) == active.as_ref() {
                        "●"
                    } else {
                        "○"
                    };
                    out.push_str(&format!("  {} {} ({})\n", marker, a.name, a.uuid));
                }
                CommandResult::Output(out)
            }
            "add" | "create" | "new" => {
                let Some(name) = rest else {
                    return CommandResult::Error("Usage: account add <username>".to_string());
                };
                match BackendBridge::create_offline_account(&name) {
                    Ok(acc) => {
                        state.accounts = BackendBridge::list_accounts()
                            .into_iter()
                            .map(|a| (a.id, a.name))
                            .collect();
                        state.active_account_name = Some(acc.name.clone());
                        CommandResult::Success(Some(format!(
                            "Created offline account '{}' (uuid {})",
                            acc.name, acc.uuid
                        )))
                    }
                    Err(e) => CommandResult::Error(e),
                }
            }
            "use" | "select" | "switch" => {
                let Some(name) = rest else {
                    return CommandResult::Error("Usage: account use <username>".to_string());
                };
                let found = BackendBridge::list_accounts()
                    .into_iter()
                    .find(|a| a.name.eq_ignore_ascii_case(&name));
                match found {
                    Some(acc) => match BackendBridge::set_active_account(&acc.id) {
                        Ok(()) => {
                            state.active_account_name = Some(acc.name.clone());
                            CommandResult::Success(Some(format!(
                                "Launch account set to '{}'",
                                acc.name
                            )))
                        }
                        Err(e) => CommandResult::Error(e),
                    },
                    None => CommandResult::Error(format!("No account named '{}'", name)),
                }
            }
            "remove" | "delete" | "rm" => {
                let Some(name) = rest else {
                    return CommandResult::Error("Usage: account remove <username>".to_string());
                };
                let found = BackendBridge::list_accounts()
                    .into_iter()
                    .find(|a| a.name.eq_ignore_ascii_case(&name));
                match found {
                    Some(acc) => match BackendBridge::delete_account(&acc.id) {
                        Ok(()) => {
                            state.accounts.retain(|(id, _)| *id != acc.id);
                            CommandResult::Success(Some(format!("Deleted account '{}'", acc.name)))
                        }
                        Err(e) => CommandResult::Error(e),
                    },
                    None => CommandResult::Error(format!("No account named '{}'", name)),
                }
            }
            other => CommandResult::Error(format!(
                "Unknown account subcommand '{}' — use: list | add <name> | use <name> | remove <name>",
                other
            )),
        }
    }

    fn cmd_settings(state: &mut AppState, args: Option<&str>) -> CommandResult {
        let settings = BackendBridge::get_settings();
        match args {
            None => {
                // Display current settings
                let java_version = state
                    .java_installations
                    .first()
                    .and_then(|j| j.version.as_ref())
                    .map(|v| format!("Java {}", v.major))
                    .unwrap_or("none".to_string());
                let output = format!(
                    "ARGUS Settings\n\
                    ──────────────\n\
                    Default Memory: {} MB\n\
                    Java Path: {}\n\
                    Theme: {}\n\
                    Language: {}\n\
                    Detected Java: {}\n\
                    \n\
                    Use: settings memory <N>, settings java auto|<path>, settings theme <dark|light|system>",
                    settings.default_memory,
                    settings.java_path.as_deref().unwrap_or("Auto-detect"),
                    settings.theme,
                    settings.language,
                    java_version,
                );
                CommandResult::Output(output)
            }
            Some(args_str) => {
                let parts: Vec<&str> = args_str.splitn(2, ' ').collect();
                let key = parts[0].to_lowercase();
                let value = parts.get(1).copied();

                match key.as_str() {
                    "memory" => {
                        if let Some(val) = value {
                            let mb: u32 = match val.parse() {
                                Ok(n) if n > 0 => n,
                                _ => {
                                    return CommandResult::Error(format!(
                                        "Invalid memory value '{}'. Use a number (e.g. 8192).",
                                        val
                                    ));
                                }
                            };
                            if BackendBridge::set_default_memory(mb) {
                                state.log(
                                    LogLevel::Info,
                                    "CMD",
                                    &format!("Memory set to {} MB", mb),
                                );
                                CommandResult::Success(Some(format!(
                                    "Default memory set to {} MB (persisted)",
                                    mb
                                )))
                            } else {
                                CommandResult::Error("Failed to save memory setting.".to_string())
                            }
                        } else {
                            CommandResult::Output(format!(
                                "Current default memory: {} MB\n\
                                Valid presets: 2048, 4096, 6144, 8192, 12288, 16384",
                                settings.default_memory
                            ))
                        }
                    }
                    "java" => {
                        if let Some(val) = value {
                            let path = if val == "auto" {
                                None
                            } else {
                                Some(val.to_string())
                            };
                            if BackendBridge::set_java_path(path.clone()) {
                                let desc = path.as_deref().unwrap_or("Auto-detect");
                                state.log(
                                    LogLevel::Info,
                                    "CMD",
                                    &format!("Java path set to {}", desc),
                                );
                                CommandResult::Success(Some(format!(
                                    "Java path set to {} (persisted)",
                                    desc
                                )))
                            } else {
                                CommandResult::Error(
                                    "Failed to save Java path setting.".to_string(),
                                )
                            }
                        } else {
                            let java_list: String = state
                                .java_installations
                                .iter()
                                .map(|j| {
                                    let v = j
                                        .version
                                        .as_ref()
                                        .map(|ver| ver.major.to_string())
                                        .unwrap_or_else(|| "?".to_string());
                                    format!("  Java {} — {}", v, j.path.to_string_lossy())
                                })
                                .collect::<Vec<_>>()
                                .join("\n");
                            CommandResult::Output(format!(
                                "Current Java: {}\n\
                                Use: settings java auto  or  settings java <path>\n\
                                Detected installations:\n{}",
                                settings.java_path.as_deref().unwrap_or("Auto-detect"),
                                java_list
                            ))
                        }
                    }
                    "theme" => {
                        if let Some(val) = value {
                            let v = val.to_lowercase();
                            if matches!(v.as_str(), "dark" | "light" | "system") {
                                if BackendBridge::set_theme(&v) {
                                    state.log(
                                        LogLevel::Info,
                                        "CMD",
                                        &format!("Theme set to {}", v),
                                    );
                                    CommandResult::Success(Some(format!(
                                        "Theme set to {} (persisted)",
                                        v
                                    )))
                                } else {
                                    CommandResult::Error(
                                        "Failed to save theme setting.".to_string(),
                                    )
                                }
                            } else {
                                CommandResult::Error(format!(
                                    "Invalid theme '{}'. Use: dark, light, or system",
                                    v
                                ))
                            }
                        } else {
                            CommandResult::Output(format!(
                                "Current theme: {}\n\
                                Valid values: dark, light, system",
                                settings.theme
                            ))
                        }
                    }
                    _ => CommandResult::Error(format!(
                        "Unknown settings key '{}'. Available: memory, java, theme, language",
                        key
                    )),
                }
            }
        }
    }

    fn cmd_java(state: &AppState) -> CommandResult {
        let mut output = String::from("Installed Java Runtimes:\n");
        output.push_str(&format!("{:<5} {:<60} {:<10}\n", "#", "Path", "Version"));
        output.push_str(&"─".repeat(80));
        output.push('\n');
        for (i, j) in state.java_installations.iter().enumerate() {
            let version = j
                .version
                .as_ref()
                .map(|v| format!("Java {}", v.major))
                .unwrap_or("Unknown".to_string());
            output.push_str(&format!(
                "{:<5} {:<60} {:<10}\n",
                i,
                j.path.to_string_lossy(),
                version
            ));
        }
        CommandResult::Output(output)
    }

    fn cmd_versions(state: &AppState) -> CommandResult {
        let mut output = String::from("Available Minecraft Versions:\n");
        for v in &state.versions {
            output.push_str(&format!("  • {}\n", v));
        }
        output.push_str("\nFabric Loader Versions:\n");
        for v in &state.fabric_versions {
            output.push_str(&format!("  • {}\n", v));
        }
        output.push_str("\nForge Versions:\n");
        for v in &state.forge_versions {
            output.push_str(&format!("  • {}\n", v));
        }
        CommandResult::Output(output)
    }

    fn cmd_update(state: &AppState) -> CommandResult {
        let url = crate::argus::update::RELEASES_PAGE;
        let open = if cfg!(windows) {
            std::process::Command::new("cmd")
                .args(["/c", "start", "", url])
                .spawn()
        } else {
            std::process::Command::new("xdg-open").arg(url).spawn()
        };
        match open {
            Ok(_) => {
                let extra = state
                    .update_available
                    .as_ref()
                    .map(|t| format!(" Latest release: {}.", t))
                    .unwrap_or_default();
                CommandResult::Success(Some(format!(
                    "Opening releases page: {}{}. Replace era-launcher.exe with the new download.",
                    url, extra
                )))
            }
            Err(e) => CommandResult::Error(format!(
                "Could not open browser ({}). Releases page: {}",
                e, url
            )),
        }
    }

    fn cmd_search(state: &mut AppState, args: Option<&str>) -> CommandResult {
        let query = args.unwrap_or("");
        state.set_loading(true, Some(format!("Searching Modrinth for '{}'...", query)));
        let results = BackendBridge::search_modrinth(query, "mod", "", "");
        let results = match results {
            Ok(r) => r,
            Err(e) => {
                state.set_loading(false, None);
                state.set_error(format!("Modrinth search failed: {}", e));
                return CommandResult::Error(format!("Search failed: {}", e));
            }
        };
        state.modrinth_results = results.clone();
        state.set_loading(false, None);
        state.log(
            LogLevel::Info,
            "BACKEND",
            &format!("Modrinth search returned {} results", results.len()),
        );

        if results.is_empty() {
            CommandResult::Success(Some(format!("No mods found for '{}'.", query)))
        } else {
            let mut output = format!("Modrinth Search Results ('{}')\n", query);
            output.push_str(&"─".repeat(80));
            output.push('\n');
            for (i, r) in results.iter().enumerate() {
                output.push_str(&format!(
                    "{:<3} {:<40} {:<10} {:<20}\n",
                    i,
                    &r.title[..r.title.len().min(40)],
                    r.downloads,
                    r.game_versions
                        .first()
                        .cloned()
                        .unwrap_or_else(|| "unknown".to_string())
                ));
            }
            CommandResult::Output(output)
        }
    }

    /// Get help text for all available commands
    pub fn help_text() -> String {
        r#"ARGUS — Minecraft Runtime Control Terminal
Available Commands:

Navigation:
  home              Navigate to HOME screen
  discover          Navigate to DISCOVER (categories inside)
  instances         Navigate to INSTANCES screen
  mods              Show content installed in the selected instance
  worlds            Navigate to WORLDS management
  logs              Navigate to LOGS viewer
  settings          Navigate to SETTINGS

Runtime:
  launch [name]     Launch Minecraft instance (selected or by name)
  stop              Stop running Minecraft process
  status            Show current runtime status

Instances:
  create [name]     Create a new instance (persisted)
                    HOME → Create walks loader → game version; DISCOVER
                    then only lists content matching that MC version.
  delete <id|name>  Delete an instance (persisted)
  edit              Edit selected instance

Settings:
  settings          Show current settings
  settings memory <N>    Set default memory (MB)
  settings java auto|<path>  Set Java path
  settings theme <dark|light|system>  Set theme (applies instantly)

Accounts (offline):
  account list                Show saved accounts
  account add <username>      Create offline account (3-16 chars, A-Za-z0-9_)
  account use <username>      Switch launch account
  account remove <username>   Delete an account

Content:
  search <query>    Search Modrinth for mods
                    In DISCOVER: [/] types a query, ENTER on a result opens
                    a version chooser (releases before alphas) — pick the
                    exact build to install. Only builds matching your
                    instance's MC version and loader are listed.
                    Categories: Mods, Modpacks, Shaders, Resource Packs.
Info:

  java              List installed Java runtimes
  versions          List available Minecraft/Fabric/Forge versions
  update            Open the latest release page in your browser
  help              Show this help message

Terminal:
  clear             Clear the terminal output
  exit / quit       Exit ARGUS

Keyboard Shortcuts:
  ← →               Switch section (focus lands inside its content)
  ↑ ↓               Move within the section's items (wraps, stays inside)
  TAB / SHIFT+TAB   Reach the navbar / cycle every control
  ENTER             Activate focused control; ENTER again on a selected
                    instance launches it
  1-4               Discover: open category and jump into results
  ESC               Discover: results → categories → main tabs;
                    elsewhere closes overlays / cancels edit
  /                 Search Modrinth (in DISCOVER)
  X                 INSTANCES: delete selected instance
                    MODS: remove the focused mod/shader/pack file
  PGUP / PGDN       Fast-step items / scroll LOGS
  CTRL+L            Focus command prompt
  ESC               Close help · cancel search/edit mode
  ?                 Toggle shortcuts overlay
  c                 Create Instance (on HOME)
  h/d/i/m/w/l/s     Section shortcuts
"#
        .to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_command() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::None));
    }

    #[test]
    fn test_unknown_command() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("nonexistent", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::Error(_)));
    }

    #[test]
    fn test_help_command() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("help", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::Help));
    }

    #[test]
    fn test_navigation_commands() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        assert!(matches!(
            CommandManager::execute("home", &mut state, &mut tracker),
            CommandResult::Navigate(Section::Home)
        ));
        assert!(matches!(
            CommandManager::execute("discover", &mut state, &mut tracker),
            CommandResult::Navigate(Section::Discover)
        ));
        assert!(matches!(
            CommandManager::execute("instances", &mut state, &mut tracker),
            CommandResult::Navigate(Section::Instances)
        ));
        // `settings` with no args shows current settings (Output, not Navigate)
        let result = CommandManager::execute("settings", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::Output(_)));
        assert!(matches!(
            CommandManager::execute("mods", &mut state, &mut tracker),
            CommandResult::Navigate(Section::Mods)
        ));
    }

    #[test]
    fn test_status_command() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("status", &mut state, &mut tracker);
        matches!(result, CommandResult::Output(_));
    }

    #[test]
    fn test_settings_command_no_args() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::default();
        let result = CommandManager::execute("settings", &mut state, &mut tracker);
        // With no args, settings command shows current settings as output
        assert!(matches!(result, CommandResult::Output(_)));
        if let CommandResult::Output(text) = result {
            assert!(text.contains("ARGUS Settings"));
            assert!(text.contains("Default Memory"));
        }
    }

    #[test]
    fn test_settings_memory_no_args_shows_current() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("settings memory", &mut state, &mut tracker);
        match result {
            CommandResult::Output(s) => assert!(s.contains("MB")),
            CommandResult::Error(e) => panic!("Expected output, got error: {}", e),
            _ => panic!("Expected output, got something else"),
        }
    }

    #[test]
    fn test_settings_invalid_memory_value() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("settings memory abc", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::Error(_)));
    }

    #[test]
    fn test_settings_invalid_theme() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("settings theme purple", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::Error(_)));
    }

    #[test]
    fn test_settings_theme_no_args_shows_current() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("settings theme", &mut state, &mut tracker);
        match result {
            CommandResult::Output(s) => assert!(s.contains("theme")),
            CommandResult::Error(e) => panic!("Expected output, got error: {}", e),
            _ => panic!("Expected output, got something else"),
        }
    }

    #[test]
    fn test_settings_java_no_args_shows_list() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("settings java", &mut state, &mut tracker);
        match result {
            CommandResult::Output(s) => assert!(s.contains("Java") || s.contains("Auto-detect")),
            CommandResult::Error(e) => panic!("Expected output, got error: {}", e),
            _ => panic!("Expected output, got something else"),
        }
    }

    #[test]
    fn test_settings_unknown_key() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("settings foo", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::Error(_)));
    }

    #[test]
    fn test_settings_memory_persists() {
        let result = BackendBridge::set_default_memory(8192);
        assert!(result, "set_default_memory should return true on success");
    }

    #[test]
    fn test_settings_theme_persists() {
        let result = BackendBridge::set_theme("light");
        assert!(result, "set_theme should return true on success");
        // Restore
        let _ = BackendBridge::set_theme("dark");
    }

    #[test]
    fn test_settings_java_auto() {
        let mut state = AppState::new();
        let mut tracker = RuntimeTracker::new();
        let result = CommandManager::execute("settings java auto", &mut state, &mut tracker);
        assert!(matches!(result, CommandResult::Success(_)));
    }

    #[test]
    fn test_settings_java_path_persists() {
        let result = BackendBridge::set_java_path(Some("C:\\Java\\bin\\java.exe".to_string()));
        assert!(result, "set_java_path should return true on success");
        // Restore to auto-detect
        let _ = BackendBridge::set_java_path(None);
    }
}
