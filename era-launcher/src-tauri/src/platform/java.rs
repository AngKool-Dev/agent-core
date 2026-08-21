use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Command;
use crate::prelude::*;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JavaVersion {
    pub major: u32,
    pub minor: u32,
    pub path: PathBuf,
}

impl JavaVersion {
    pub fn parse_output(path: &Path, output: &str) -> Option<Self> {
        let version = output.lines().find(|l| l.contains("version"))?;
        let num_str = version
            .chars()
            .filter(|c| c.is_numeric() || *c == '.')
            .collect::<String>();
        let parts: Vec<&str> = num_str.split('.').collect();
        let major = parts.first()?.parse().ok()?;
        let minor = parts.get(1).and_then(|v| v.parse().ok()).unwrap_or(0);
        Some(Self { major, minor, path: path.to_path_buf() })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JavaInstallation {
    pub path: PathBuf,
    pub version: Option<JavaVersion>,
}

pub struct JavaManager;

impl JavaManager {
    pub fn detect_all() -> Vec<JavaInstallation> {
        let mut installs = Vec::new();
        let candidates = Self::candidate_paths();
        for path in candidates {
            if let Ok(output) = Self::run_java_version(&path) {
                if let Some(version) = JavaVersion::parse_output(&path, &output) {
                    installs.push(JavaInstallation { path, version: Some(version) });
                } else {
                    installs.push(JavaInstallation { path, version: None });
                }
            }
        }
        installs
    }

    pub fn find_compatible(required_major: u32) -> Option<JavaInstallation> {
        let installs = Self::detect_all();
        installs.into_iter().filter(|i| i.version.as_ref().map(|v| v.major) == Some(required_major)).next()
    }

    pub fn required_for_minecraft(version: &str) -> u32 {
        let major = version.split('.').next().and_then(|v| v.parse::<u32>().ok()).unwrap_or(1);
        match major {
            1..=16 => 8,
            17 => 17,
            _ => 21,
        }
    }

    fn candidate_paths() -> Vec<PathBuf> {
        let mut paths = Vec::new();
        let bin_name = if cfg!(windows) { "java.exe" } else { "java" };

        if let Some(java_home) = std::env::var_os("JAVA_HOME") {
            let p = PathBuf::from(java_home).join("bin").join(bin_name);
            paths.push(p);
        }

        if let Some(path) = std::env::var_os("PATH") {
            for dir in std::env::split_paths(&path) {
                paths.push(dir.join(bin_name));
            }
        }

        if cfg!(windows) {
            let program_files = std::env::var("ProgramFiles").unwrap_or_default();
            let program_files_x86 = std::env::var("ProgramFiles(x86)").unwrap_or_default();
            let local_app_data = std::env::var("LOCALAPPDATA").unwrap_or_default();

            for base in [program_files, program_files_x86, local_app_data] {
                if base.is_empty() { continue; }
                if let Ok(entries) = std::fs::read_dir(base) {
                    for entry in entries.flatten() {
                        let p = entry.path().join("bin").join(bin_name);
                        paths.push(p);
                    }
                }
            }
        }

        paths
    }

    fn run_java_version(path: &Path) -> Result<String> {
        let output = Command::new(path)
            .arg("-version")
            .output()
            .map_err(|e| LauncherError::Process(format!("Failed to run java: {}", e)))?;
        let text = String::from_utf8_lossy(&output.stderr).to_string();
        Ok(text)
    }
}
