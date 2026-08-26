use crate::prelude::*;
use reqwest::Client;
use serde::{Deserialize, Serialize};

const MOJANG_MANIFEST: &str = "https://launchermeta.mojang.com/mc/game/version_manifest.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
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
    #[serde(rename = "majorVersion")]
    pub major: u32,
    pub component: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LibraryInfo {
    pub name: String,
    pub downloads: Option<LibraryDownloads>,
    pub rules: Option<serde_json::Value>,
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
pub struct Arguments {
    pub game: Vec<serde_json::Value>,
    pub jvm: Vec<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Downloads {
    pub client: Option<ArtifactInfo>,
    pub server: Option<ArtifactInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssetIndex {
    pub id: String,
    pub url: String,
    pub sha1: String,
    pub size: u64,
}

pub struct ManifestClient {
    client: Client,
}

impl ManifestClient {
    pub fn new() -> Result<Self> {
        Ok(Self {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(30))
                .build()?,
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

        let versions = manifest
            .get("versions")
            .and_then(|v| v.as_array())
            .ok_or_else(|| LauncherError::Minecraft("Invalid manifest".to_string()))?;
        for v in versions {
            if v.get("id").and_then(|i| i.as_str()) == Some(version_id) {
                let url = v
                    .get("url")
                    .and_then(|u| u.as_str())
                    .ok_or_else(|| LauncherError::Minecraft("Missing version URL".to_string()))?;
                let info: ManifestVersionInfo = self
                    .client
                    .get(url)
                    .header("User-Agent", "EraLauncher/0.1.0")
                    .send()
                    .await?
                    .json()
                    .await?;
                return Ok(info);
            }
        }
        Err(LauncherError::NotFound(format!(
            "Version {} not found",
            version_id
        )))
    }

    pub async fn get_all_versions(&self) -> Result<Vec<String>> {
        let manifest: serde_json::Value = self
            .client
            .get(MOJANG_MANIFEST)
            .header("User-Agent", "EraLauncher/0.1.0")
            .send()
            .await?
            .json()
            .await?;

        let versions = manifest
            .get("versions")
            .and_then(|v| v.as_array())
            .ok_or_else(|| LauncherError::Minecraft("Invalid manifest".to_string()))?;
        let mut result = Vec::new();
        for v in versions {
            if let Some(id) = v.get("id").and_then(|i| i.as_str()) {
                result.push(id.to_string());
            }
        }
        Ok(result)
    }

    /// Release versions only (no snapshots/old_beta/old_alpha), newest
    /// first — used by the create-instance version picker.
    pub async fn get_release_versions(&self) -> Result<Vec<String>> {
        let manifest: serde_json::Value = self
            .client
            .get(MOJANG_MANIFEST)
            .header("User-Agent", "EraLauncher/0.1.0")
            .send()
            .await?
            .json()
            .await?;

        let versions = manifest
            .get("versions")
            .and_then(|v| v.as_array())
            .ok_or_else(|| LauncherError::Minecraft("Invalid manifest".to_string()))?;
        let mut result = Vec::new();
        for v in versions {
            if v.get("type").and_then(|t| t.as_str()) != Some("release") {
                continue;
            }
            if let Some(id) = v.get("id").and_then(|i| i.as_str()) {
                result.push(id.to_string());
            }
        }
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_manifest_version_info_deserialize() {
        let json = r#"{
            "id": "1.21.1",
            "type": "release",
            "mainClass": "net.minecraft.client.main.Main",
            "javaVersion": {"majorVersion": 21, "component": "java-runtime-delta"},
            "libraries": [
                {
                    "name": "com.mojang:brigadier:1.0.18",
                    "downloads": {
                        "artifact": {
                            "url": "https://piston-data.mojang.com/v1/objects/abc123",
                            "sha1": "abc123def456",
                            "size": 12345
                        }
                    }
                }
            ],
            "arguments": {
                "game": ["--username ${auth_player_name}"],
                "jvm": ["-Xmx${MAX_MEMORY}M"]
            },
            "downloads": {
                "client": {
                    "url": "https://piston-data.mojang.com/v1/objects/client123",
                    "sha1": "client_sha1",
                    "size": 50000
                }
            },
            "assetIndex": {
                "id": "1.21.1",
                "url": "https://piston-data.mojang.com/v1/objects/asset123",
                "sha1": "asset_sha1",
                "size": 1000
            }
        }"#;
        let info: ManifestVersionInfo = serde_json::from_str(json).unwrap();
        assert_eq!(info.id, "1.21.1");
        assert_eq!(info.version_type, "release");
        assert_eq!(
            info.main_class,
            Some("net.minecraft.client.main.Main".to_string())
        );
        assert_eq!(info.java_version.unwrap().major, 21);
        assert_eq!(info.libraries.len(), 1);
        assert_eq!(info.libraries[0].name, "com.mojang:brigadier:1.0.18");
        assert!(info.arguments.is_some());
        assert!(info.downloads.is_some());
        assert!(info.asset_index.id == "1.21.1");
    }

    #[test]
    fn test_manifest_with_rules_and_classifiers() {
        let json = r#"{
            "id": "1.20.1",
            "type": "release",
            "mainClass": "net.minecraft.client.main.Main",
            "javaVersion": {"majorVersion": 17, "component": "java-runtime-delta"},
            "libraries": [
                {
                    "name": "net.minecraft:launchwrapper:1.5.2",
                    "downloads": {
                        "classifiers": {
                            "natives-windows-x86_64": {
                                "url": "https://example.com/natives-windows",
                                "sha1": "nat_sha1",
                                "size": 5000
                            }
                        }
                    },
                    "rules": [{"action": "allow", "os": {"name": "windows"}}]
                }
            ],
            "arguments": null,
            "downloads": null,
            "assetIndex": {
                "id": "1.20.1",
                "url": "https://example.com/asset",
                "sha1": "abc",
                "size": 100
            }
        }"#;
        let info: ManifestVersionInfo = serde_json::from_str(json).unwrap();
        assert!(
            info.libraries[0]
                .downloads
                .as_ref()
                .unwrap()
                .classifiers
                .is_some()
        );
    }

    #[test]
    fn test_manifest_arguments_deserialize() {
        let json = r#"{"game": [], "jvm": []}"#;
        let args: Arguments = serde_json::from_str(json).unwrap();
        assert!(args.game.is_empty());
        assert!(args.jvm.is_empty());
    }

    #[test]
    fn test_artifact_info_deserialize() {
        let json = r#"{"url": "https://example.com", "sha1": "abc123", "size": 1024}"#;
        let artifact: ArtifactInfo = serde_json::from_str(json).unwrap();
        assert_eq!(artifact.url, "https://example.com");
        assert_eq!(artifact.sha1, "abc123");
        assert_eq!(artifact.size, 1024);
    }

    #[test]
    fn test_asset_index_deserialize() {
        let json = r#"{"id": "1.20.1", "url": "https://example.com", "sha1": "abc", "size": 100}"#;
        let idx: AssetIndex = serde_json::from_str(json).unwrap();
        assert_eq!(idx.id, "1.20.1");
        assert_eq!(idx.url, "https://example.com");
        assert_eq!(idx.sha1, "abc");
        assert_eq!(idx.size, 100);
    }
}
