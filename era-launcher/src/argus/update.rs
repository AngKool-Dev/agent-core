//! Release update checking against the public GitHub distribution repo.

use std::time::{Duration, Instant};

const LATEST_RELEASE_API: &str =
    "https://api.github.com/repos/AngKool-Dev/argus-releases/releases/latest";

pub const RELEASES_PAGE: &str = "https://github.com/AngKool-Dev/argus-releases/releases/latest";

const CHECK_INTERVAL: Duration = Duration::from_secs(60 * 60); // 1 hour
const REQUEST_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_RETRIES: u32 = 3;
const INITIAL_RETRY_DELAY: Duration = Duration::from_millis(500);

#[derive(Debug, Clone)]
pub enum UpdateCheckResult {
    UpToDate,
    UpdateAvailable(String),
    CheckFailed(String),
}

/// Spawns a detached thread that fetches the latest published release tag
/// with retries and backoff. Sends exactly one message with the result.
pub fn spawn_check(
    current_version: &'static str,
    last_check: Option<Instant>,
) -> std::sync::mpsc::Receiver<UpdateCheckResult> {
    let (tx, rx) = std::sync::mpsc::channel();

    if let Some(last) = last_check {
        if last.elapsed() < CHECK_INTERVAL {
            let _ = tx.send(UpdateCheckResult::UpToDate);
            return rx;
        }
    }

    std::thread::spawn(move || {
        let result = fetch_with_retry(current_version);
        let _ = tx.send(result);
    });
    rx
}

fn fetch_with_retry(current_version: &str) -> UpdateCheckResult {
    let mut attempt = 0;
    let mut delay = INITIAL_RETRY_DELAY;

    loop {
        attempt += 1;
        match fetch_latest_tag() {
            Ok(Some(tag)) => {
                if crate::argus::state::AppState::is_newer_version(&tag, current_version) {
                    return UpdateCheckResult::UpdateAvailable(tag);
                } else {
                    return UpdateCheckResult::UpToDate;
                }
            }
            Ok(None) => return UpdateCheckResult::UpToDate,
            Err(e) => {
                if attempt >= MAX_RETRIES {
                    return UpdateCheckResult::CheckFailed(format!(
                        "Update check failed after {} attempts: {}",
                        attempt, e
                    ));
                }
                std::thread::sleep(delay);
                delay *= 2;
            }
        }
    }
}

fn fetch_latest_tag() -> Result<Option<String>, String> {
    let rt = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
    rt.block_on(async {
        let client = reqwest::Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .build()
            .map_err(|e| e.to_string())?;
        let resp = client
            .get(LATEST_RELEASE_API)
            .header(
                "User-Agent",
                concat!("EraLauncher/", env!("CARGO_PKG_VERSION")),
            )
            .send()
            .await
            .map_err(|e| e.to_string())?;

        if !resp.status().is_success() {
            return Err(format!("GitHub API returned {}", resp.status()));
        }

        let json: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
        let tag = json
            .get("tag_name")
            .and_then(|s| s.as_str())
            .map(|s| s.trim().to_string());
        Ok(tag)
    })
}

/// Fetch the full latest release JSON and return the browser_download_url
/// for the first asset named `era-launcher.exe`.
pub fn fetch_latest_asset_url() -> Result<String, String> {
    let rt = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
    rt.block_on(async {
        let client = reqwest::Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .build()
            .map_err(|e| e.to_string())?;
        let resp = client
            .get(LATEST_RELEASE_API)
            .header(
                "User-Agent",
                concat!("EraLauncher/", env!("CARGO_PKG_VERSION")),
            )
            .send()
            .await
            .map_err(|e| e.to_string())?;

        if !resp.status().is_success() {
            return Err(format!("GitHub API returned {}", resp.status()));
        }

        let json: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
        let assets = json
            .get("assets")
            .and_then(|a| a.as_array())
            .ok_or_else(|| "Release has no assets".to_string())?;

        for asset in assets {
            let name = asset.get("name").and_then(|n| n.as_str()).unwrap_or("");
            if name == "era-launcher.exe" {
                let url = asset
                    .get("browser_download_url")
                    .and_then(|u| u.as_str())
                    .ok_or_else(|| "Asset missing browser_download_url".to_string())?;
                return Ok(url.to_string());
            }
        }
        Err("era-launcher.exe asset not found in latest release".to_string())
    })
}

/// Download a file from `url` to `dest` with no progress reporting.
pub fn download_asset(url: &str, dest: &std::path::Path) -> Result<(), String> {
    let rt = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
    rt.block_on(async {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(120))
            .build()
            .map_err(|e| e.to_string())?;
        let resp = client
            .get(url)
            .header(
                "User-Agent",
                concat!("EraLauncher/", env!("CARGO_PKG_VERSION")),
            )
            .send()
            .await
            .map_err(|e| e.to_string())?;

        if !resp.status().is_success() {
            return Err(format!("Download HTTP {}", resp.status()));
        }

        let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
        std::fs::write(dest, bytes).map_err(|e| e.to_string())?;
        Ok(())
    })
}

/// Create a Windows `.bat` helper that waits for the current process to exit,
/// copies `new_exe` over `current_exe`, deletes itself, and relaunches.
pub fn create_update_helper(
    current_exe: &std::path::Path,
    new_exe: &std::path::Path,
) -> Result<std::path::PathBuf, String> {
    let helper_path = current_exe.with_extension("bat");
    let current_exe_str = current_exe.to_string_lossy().replace("\\", "/");
    let new_exe_str = new_exe.to_string_lossy().replace("\\", "/");
    let helper_str = helper_path.to_string_lossy().replace("\\", "/");

    let script = format!(
        r#"@echo off
setlocal
set "CURRENT={}"
set "NEW={}"
set "HELPER={}"
:waitloop
tasklist /fi "imagename eq era-launcher.exe" 2>NUL | findstr /i "era-launcher.exe" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto waitloop
)
copy /Y "%NEW%" "%CURRENT%" >NUL 2>&1
del /f /q "%NEW%" >NUL 2>&1
del /f /q "%HELPER%" >NUL 2>&1
start "" "%CURRENT%"
"#,
        current_exe_str, new_exe_str, helper_str
    );

    std::fs::write(&helper_path, script).map_err(|e| e.to_string())?;
    Ok(helper_path)
}
