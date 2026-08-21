use crate::prelude::*;
use reqwest::Client;
use serde::{Deserialize, Serialize};

const MOJANG_MANIFEST: &str = "https://launchermeta.mojang.com/mc/game/version_manifest.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManifestVersionInfo {
    pub id: String,
    #[serde(rename = "type")]
    pub version_type: String,
    pub main_class: Option<String>,
    pub java_version: Option<JavaVersionInfo>,
    pub libraries: Vec<LibraryInfo>,
    pub arguments: Option<Arguments>,
    pub downloads: Option<Downloads>,
    pub asset_index: AssetIndex,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JavaVersionInfo {
    pub major: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LibraryInfo {
    pub name: String,
    pub url: Option<String>,
    pub downloads: Option<LibraryDownloads>,
    pub rules: Option<serde_json::Value>,
    pub natives: Option<NativesInfo>,
    pub artifact: Option<ArtifactInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LibraryDownloads {
    pub artifact: Option<ArtifactInfo>,
    pub classifiers: Option<std::collections::HashMap<String, ArtifactInfo>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArtifactInfo {
    pub url: String,
    pub sha1: String,
    pub size: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleInfo {
    pub action: Option<String>,
    pub os: Option<OsRule>,
    pub features: Option<std::collections::HashMap<String, bool>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OsRule {
    pub name: Option<String>,
    pub arch: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NativesInfo {
    pub windows: Option<String>,
    pub linux: Option<String>,
    pub osx: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Arguments {
    pub game: Vec<serde_json::Value>,
    pub jvm: Vec<serde_json::Value>,
    #[serde(default)]
    pub default_user_jvm: Vec<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Downloads {
    pub client: Option<ArtifactInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssetIndex {
    pub id: String,
    pub url: String,
}

pub struct ManifestClient {
    client: Client,
}

impl ManifestClient {
    pub fn new() -> Result<Self> {
        Ok(Self {
            client: Client::builder().timeout(std::time::Duration::from_secs(30)).build()?,
        })
    }

    pub async fn get_version_info_by_id(&self, version_id: &str) -> Result<ManifestVersionInfo> {
        let manifest: serde_json::Value = self
            .client
            .get(MOJANG_MANIFEST)
            .header("User-Agent", "EraLauncher/0.1.0")
            .send()
            .await?
            .json()
            .await?;

        let versions = manifest.get("versions").and_then(|v| v.as_array()).ok_or_else(|| LauncherError::Minecraft("Invalid manifest".to_string()))?;
        for v in versions {
            if v.get("id").and_then(|i| i.as_str()) == Some(version_id) {
                let url = v.get("url").and_then(|u| u.as_str()).ok_or_else(|| LauncherError::Minecraft("Missing version URL".to_string()))?;
                let info: ManifestVersionInfo = self.client.get(url).header("User-Agent", "EraLauncher/0.1.0").send().await?.json().await?;
                return Ok(info);
            }
        }
        Err(LauncherError::NotFound(format!("Version {} not found", version_id)))
    }
}
