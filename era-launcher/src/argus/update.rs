//! Release update checking against the public GitHub distribution repo.

const LATEST_RELEASE_API: &str =
    "https://api.github.com/repos/AngKool-Dev/argus-releases/releases/latest";

pub const RELEASES_PAGE: &str = "https://github.com/AngKool-Dev/argus-releases/releases/latest";

/// Spawns a detached thread that fetches the latest published release tag.
/// Sends exactly one message: `Some(tag)` when it is newer than
/// `current_version`, otherwise `None` (up-to-date, offline, or any error).
pub fn spawn_check(current_version: &'static str) -> std::sync::mpsc::Receiver<Option<String>> {
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let latest = fetch_latest_tag();
        let newer = latest
            .as_deref()
            .filter(|tag| crate::argus::state::AppState::is_newer_version(tag, current_version))
            .map(|tag| tag.to_string());
        let _ = tx.send(newer);
    });
    rx
}

fn fetch_latest_tag() -> Option<String> {
    let rt = tokio::runtime::Runtime::new().ok()?;
    rt.block_on(async {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(5))
            .build()
            .ok()?;
        let resp = client
            .get(LATEST_RELEASE_API)
            .header(
                "User-Agent",
                concat!("EraLauncher/", env!("CARGO_PKG_VERSION")),
            )
            .send()
            .await
            .ok()?;
        if !resp.status().is_success() {
            return None;
        }
        let json: serde_json::Value = resp.json().await.ok()?;
        json.get("tag_name")?.as_str().map(|s| s.trim().to_string())
    })
}
