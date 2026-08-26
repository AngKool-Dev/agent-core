use crate::prelude::*;
use reqwest::Client;
use serde::{Deserialize, Serialize};

const MODRINTH_API: &str = "https://api.modrinth.com/v2";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    #[serde(rename = "project_id")]
    pub id: String,
    pub title: String,
    pub description: String,
    pub icon_url: Option<String>,
    pub downloads: u64,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub categories: Vec<String>,
    #[serde(default)]
    pub gallery: Vec<String>,
    #[serde(default)]
    pub versions: Vec<String>,
    #[serde(default)]
    pub game_versions: Vec<String>,
    #[serde(default)]
    pub loaders: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Version {
    pub id: String,
    #[serde(default)]
    pub project_id: String,
    #[serde(default)]
    pub version_number: String,
    /// "release" | "beta" | "alpha" — used for labels and release-first
    /// auto-picking.
    #[serde(default)]
    pub version_type: String,
    #[serde(default)]
    pub date_published: String,
    #[serde(default)]
    pub game_versions: Vec<String>,
    #[serde(default)]
    pub loaders: Vec<String>,
    #[serde(default)]
    pub files: Vec<VersionFile>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VersionFile {
    pub url: String,
    pub filename: String,
    pub size: u64,
    pub file_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub hits: Vec<Project>,
}

pub struct ModrinthClient {
    client: Client,
}

impl ModrinthClient {
    pub fn new() -> Result<Self> {
        Ok(Self {
            client: Client::builder()
                .timeout(std::time::Duration::from_secs(30))
                .build()?,
        })
    }

    pub async fn search(
        &self,
        query: &str,
        limit: usize,
        offset: usize,
        facets: &[String],
        index: Option<&str>,
    ) -> Result<SearchResult> {
        let mut request = self
            .client
            .get(format!("{}/search", MODRINTH_API))
            .header("User-Agent", "EraLauncher/0.1.0");
        if !query.is_empty() {
            request = request.query(&[("query", query)]);
        }
        if !facets.is_empty() {
            let facets_json = serde_json::to_string(
                &facets
                    .iter()
                    .map(|f| vec![f.as_str()])
                    .collect::<Vec<Vec<&str>>>(),
            )
            .unwrap_or_default();
            request = request.query(&[("facets", &facets_json)]);
        }
        if let Some(idx) = index {
            request = request.query(&[("index", idx)]);
        }
        request = request.query(&[
            ("limit", &limit.to_string()),
            ("offset", &offset.to_string()),
        ]);
        let resp = request.send().await?;
        if !resp.status().is_success() {
            return Err(LauncherError::Modrinth(format!("HTTP {}", resp.status())));
        }
        let result: SearchResult = resp.json().await?;
        Ok(result)
    }

    pub async fn get_project_versions(&self, project_id: &str) -> Result<Vec<Version>> {
        let resp = self
            .client
            .get(format!("{}/project/{}/version", MODRINTH_API, project_id))
            .header("User-Agent", "EraLauncher/0.1.0")
            .send()
            .await?;
        if !resp.status().is_success() {
            return Err(LauncherError::Modrinth(format!("HTTP {}", resp.status())));
        }
        let versions: Vec<Version> = resp.json().await?;
        Ok(versions)
    }

    #[allow(dead_code)]
    pub async fn get_fabric_loader_versions(
        &self,
        game_version: &str,
        limit: usize,
    ) -> Result<Vec<String>> {
        let resp = self
            .client
            .get(format!("{}/version", MODRINTH_API))
            .header("User-Agent", "EraLauncher/0.1.0")
            .query(&[
                ("loaders", "fabric"),
                ("game_versions", game_version),
                ("limit", &limit.to_string()),
            ])
            .send()
            .await?;
        if !resp.status().is_success() {
            return Err(LauncherError::Modrinth(format!("HTTP {}", resp.status())));
        }
        let versions: Vec<Version> = resp.json().await?;
        let mut loader_versions: Vec<String> = versions
            .iter()
            .filter_map(|v| {
                if v.loaders.contains(&"fabric".to_string()) {
                    Some(v.version_number.clone())
                } else {
                    None
                }
            })
            .collect();
        loader_versions.sort();
        loader_versions.dedup();
        Ok(loader_versions)
    }

    #[allow(dead_code)]
    pub async fn get_forge_versions(
        &self,
        game_version: &str,
        limit: usize,
    ) -> Result<Vec<String>> {
        let resp = self
            .client
            .get(format!("{}/version", MODRINTH_API))
            .header("User-Agent", "EraLauncher/0.1.0")
            .query(&[
                ("loaders", "forge"),
                ("game_versions", game_version),
                ("limit", &limit.to_string()),
            ])
            .send()
            .await?;
        if !resp.status().is_success() {
            return Err(LauncherError::Modrinth(format!("HTTP {}", resp.status())));
        }
        let versions: Vec<Version> = resp.json().await?;
        let mut loader_versions: Vec<String> = versions
            .iter()
            .filter_map(|v| {
                if v.loaders.contains(&"forge".to_string()) {
                    Some(v.version_number.clone())
                } else {
                    None
                }
            })
            .collect();
        loader_versions.sort();
        loader_versions.dedup();
        Ok(loader_versions)
    }
}
