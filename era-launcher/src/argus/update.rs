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

    // Skip check if we checked recently
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
                delay *= 2; // exponential backoff
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
        let tag = json.get("tag_name")
            .and_then(|s| s.as_str())
            .map(|s| s.trim().to_string());
        Ok(tag)
    })
}
