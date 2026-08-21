use crate::prelude::*;
use std::io::Write;
use std::path::Path;
use std::sync::Arc;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct DownloadProgress {
    pub file_name: String,
    pub bytes_downloaded: usize,
    pub total_bytes: Option<usize>,
    pub is_complete: bool,
}

pub struct DownloadManager {
    client: reqwest::Client,
    on_progress: Option<Arc<dyn Fn(DownloadProgress) + Send + Sync>>,
}

impl DownloadManager {
    pub fn new() -> Self {
        Self {
            client: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(300))
                .build()
                .unwrap_or_default(),
            on_progress: None,
        }
    }

    pub fn with_progress_callback(
        mut self,
        cb: Arc<dyn Fn(DownloadProgress) + Send + Sync>,
    ) -> Self {
        self.on_progress = Some(cb);
        self
    }

    pub async fn download(&self, url: &str, dest: &Path) -> Result<()> {
        let temp_dest = dest.with_extension("part");
        let response = self
            .client
            .get(url)
            .header("User-Agent", "EraLauncher/0.1.0")
            .send()
            .await?;
        if !response.status().is_success() {
            return Err(LauncherError::Download(format!(
                "HTTP {}",
                response.status()
            )));
        }
        std::fs::create_dir_all(dest.parent().unwrap_or(Path::new(".")))?;
        let mut file = std::fs::File::create(&temp_dest)?;
        let mut downloaded: usize = 0;
        let total = response.content_length().map(|t| t as usize);
        let name = dest
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown")
            .to_string();
        let mut stream = response.bytes_stream();
        use futures::StreamExt;
        while let Some(chunk) = stream.next().await {
            let chunk = chunk?;
            file.write_all(&chunk)?;
            downloaded += chunk.len();
            if let Some(ref cb) = self.on_progress {
                cb(DownloadProgress {
                    file_name: name.clone(),
                    bytes_downloaded: downloaded,
                    total_bytes: total,
                    is_complete: false,
                });
            }
        }
        std::fs::rename(&temp_dest, dest)?;
        if let Some(ref cb) = self.on_progress {
            cb(DownloadProgress {
                file_name: name,
                bytes_downloaded: downloaded,
                total_bytes: total,
                is_complete: true,
            });
        }
        Ok(())
    }

    pub async fn verify_sha1(&self, path: &Path, expected: &str) -> Result<bool> {
        use sha1::{Digest, Sha1};
        let mut file = std::fs::File::open(path)?;
        let mut hasher = Sha1::new();
        let mut buffer = [0u8; 8192];
        loop {
            let n = std::io::Read::read(&mut file, &mut buffer)?;
            if n == 0 {
                break;
            }
            hasher.update(&buffer[..n]);
        }
        let hash = hex::encode(hasher.finalize());
        Ok(hash.eq_ignore_ascii_case(expected))
    }
}
