mod auth;
mod config;
mod downloads;
mod errors;
mod instances;
mod launch;
mod minecraft;
mod modrinth;
mod platform;
mod prelude;
mod versions;

use std::sync::Mutex;
use once_cell::sync::Lazy;

use crate::config::Config;
use crate::instances::InstanceManager;
use crate::launch::LaunchEngine;
use crate::minecraft::java::JavaManager;
use crate::modrinth::{ModrinthClient, Project, Version};
use crate::versions::{SystemScanner, ScanResult};

static CONFIG: Lazy<Mutex<Config>> = Lazy::new(|| Mutex::new(Config::default()));
static INSTANCE_MANAGER: Lazy<Mutex<InstanceManager>> = Lazy::new(|| Mutex::new(InstanceManager::new()));

#[tauri::command]
fn get_config() -> Config {
    CONFIG.lock().unwrap().clone()
}

#[tauri::command]
fn save_config(config: Config) -> tauri::Result<()> {
    config.save().map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))?;
    *CONFIG.lock().unwrap() = config;
    Ok(())
}

#[tauri::command]
fn list_instances() -> Vec<crate::instances::InstanceConfig> {
    INSTANCE_MANAGER.lock().unwrap().list().to_vec()
}

#[tauri::command]
fn create_instance(instance: crate::instances::InstanceConfig) -> crate::instances::InstanceConfig {
    let mut m = INSTANCE_MANAGER.lock().unwrap();
    m.add(instance.clone());
    instance
}

#[tauri::command]
fn delete_instance(id: String) -> bool {
    INSTANCE_MANAGER.lock().unwrap().remove(&id)
}

#[tauri::command]
fn update_instance(instance: crate::instances::InstanceConfig) -> bool {
    INSTANCE_MANAGER.lock().unwrap().update(instance)
}

#[tauri::command]
fn scan_versions() -> Vec<ScanResult> {
    SystemScanner::new().scan().unwrap_or_default()
}

#[tauri::command]
fn get_versions() -> Vec<String> {
    vec!["1.21.1".to_string(), "1.20.4".to_string(), "1.20.1".to_string()]
}

#[tauri::command]
async fn launch_instance(req: crate::launch::LaunchRequest, instances_dir: String) -> tauri::Result<crate::launch::LaunchResult> {
    let engine = LaunchEngine::new().map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))?;
    let path = std::path::PathBuf::from(instances_dir);
    engine.launch(&req, &path).await.map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))
}

#[tauri::command]
async fn search_modrinth(query: String, content_type: String, _game_version: String, _loader: String) -> tauri::Result<Vec<Project>> {
    let client = ModrinthClient::new().map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))?;
    let facets = vec![format!("project_type:{}", content_type)];
    let result = client.search(&query, 20, 0, &facets, Some("downloads")).await.map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))?;
    Ok(result.hits)
}

#[tauri::command]
async fn get_mod_versions(project_id: String) -> tauri::Result<Vec<Version>> {
    let client = ModrinthClient::new().map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))?;
    client.get_project_versions(&project_id).await.map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))
}

#[tauri::command]
async fn install_mod(project_id: String, _version_id: String, file_url: String, file_name: String, instance_id: String, content_type: String, instances_dir: String) -> tauri::Result<()> {
    let base = std::path::PathBuf::from(instances_dir).join(instance_id);
    let dest_dir = match content_type.as_str() {
        "modpack" => base.join("modpacks"),
        "resourcepack" => base.join("resourcepacks"),
        "shader" => base.join("shaderpacks"),
        _ => base.join("mods"),
    };
    std::fs::create_dir_all(&dest_dir)?;
    let dest = dest_dir.join(&file_name);
    let dm = crate::downloads::DownloadManager::new();
    dm.download(&file_url, &dest).await.map_err(|e| tauri::Error::from(anyhow::anyhow!(e)))?;
    Ok(())
}

#[tauri::command]
fn get_java_installations() -> Vec<crate::minecraft::java::JavaInstallation> {
    JavaManager::detect_all()
}

#[tauri::command]
fn get_launcher_config_dir() -> String {
    crate::platform::Paths::new().config_dir().to_string_lossy().to_string()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            get_config,
            save_config,
            list_instances,
            create_instance,
            delete_instance,
            update_instance,
            scan_versions,
            get_versions,
            launch_instance,
            search_modrinth,
            get_mod_versions,
            install_mod,
            get_java_installations,
            get_launcher_config_dir
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
