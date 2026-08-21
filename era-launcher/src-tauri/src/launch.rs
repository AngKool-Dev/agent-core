use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Arc;
use crate::prelude::*;
use crate::downloads::DownloadProgress;
use crate::minecraft::manifest::{ManifestClient, ManifestVersionInfo};
use crate::minecraft::java::JavaManager;
use crate::minecraft::arguments::ArgumentBuilder;
use crate::platform::Paths;
use crate::config::InstanceConfig;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct LaunchRequest {
    pub instance_id: String,
    pub account_name: String,
    pub account_uuid: String,
    pub java_path: Option<String>,
    pub minecraft_dir: Option<String>,
    pub fresh: bool,
    pub memory: u32,
    pub game_version: String,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct LaunchResult {
    pub success: bool,
    pub pid: Option<u32>,
    pub exit_code: Option<i32>,
    pub message: String,
}

pub struct LaunchEngine {
    manifest: ManifestClient,
}

impl LaunchEngine {
    pub fn new() -> Result<Self> {
        Ok(Self { manifest: ManifestClient::new()? })
    }

    pub async fn launch(&self, req: &LaunchRequest, instances_dir: &Path) -> Result<LaunchResult> {
        let instance_dir = instances_dir.join(&req.instance_id);
        let mc_dir = req.minecraft_dir.as_deref().map(PathBuf::from).unwrap_or_else(|| Paths::new().default_minecraft_dir());

        let java_path = if let Some(ref j) = req.java_path {
            PathBuf::from(j)
        } else {
            let required = JavaManager::required_for_minecraft(&req.game_version);
            JavaManager::find_compatible(required)
                .ok_or_else(|| LauncherError::Java("No compatible Java found".to_string()))?
                .path
        };

        let version_info = self.manifest.get_version_info_by_id(&req.game_version).await?;
        let _client_jar = self.download_client(&version_info, &instance_dir, req.fresh).await?;
        let _libs = self.download_libraries(&version_info, &instance_dir, req.fresh).await?;
        let natives_dir = self.extract_natives(&version_info, &instance_dir)?;
        let game_dir = if mc_dir.join("versions").join(&req.game_version).exists() {
            mc_dir.join("versions").join(&req.game_version)
        } else {
            instance_dir.clone()
        };
        let assets_dir = mc_dir.join("assets");

        let (jvm_args, game_args, main_class) = self.build_args(&version_info, req, &game_dir, &assets_dir, &natives_dir, req.memory);
        let classpath = self.build_classpath(&instance_dir, &version_info, &natives_dir);

        let mut cmd = Command::new(&java_path);
        for arg in &jvm_args { cmd.arg(arg); }
        cmd.arg("-cp").arg(&classpath).arg(&main_class);
        for arg in &game_args { cmd.arg(arg); }
        cmd.current_dir(&game_dir).stdin(std::process::Stdio::null()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::piped());

        let child = cmd.spawn().map_err(|e| LauncherError::Process(format!("Failed to spawn: {}", e)))?;
        let pid = child.id();

        let output = child.wait_with_output().map_err(|e| LauncherError::Process(format!("Failed to wait: {}", e)))?;
        let exit_code = output.status.code();

        Ok(LaunchResult {
            success: output.status.success(),
            pid: Some(pid),
            exit_code,
            message: if output.status.success() { "Minecraft exited successfully".to_string() } else { "Minecraft exited with error".to_string() },
        })
    }

    async fn download_client(&self, info: &ManifestVersionInfo, root: &Path, fresh: bool) -> Result<PathBuf> {
        let versions_dir = root.join("versions").join(&info.id);
        std::fs::create_dir_all(&versions_dir)?;
        let client_path = versions_dir.join(format!("{}.jar", info.id));
        if client_path.exists() && !fresh {
            return Ok(client_path);
        }
        if let Some(ref dl) = info.downloads.as_ref().and_then(|d| d.client.as_ref()) {
            let dm = crate::downloads::DownloadManager::new();
            dm.download(&dl.url, &client_path).await?;
        }
        Ok(client_path)
    }

    async fn download_libraries(&self, info: &ManifestVersionInfo, root: &Path, _fresh: bool) -> Result<Vec<PathBuf>> {
        let libs_dir = root.join("libraries");
        let mut paths = Vec::new();
        for lib in &info.libraries {
            if !self.library_applies(&lib.rules) { continue; }
            let path = self.resolve_library_path(&lib.name, &libs_dir);
            if let Some(ref artifact) = lib.artifact {
                if !artifact.url.is_empty() && !path.exists() {
                    let dm = crate::downloads::DownloadManager::new();
                    let _ = dm.download(&artifact.url, &path).await;
                }
            }
            paths.push(path);
        }
        Ok(paths)
    }

    fn extract_natives(&self, _info: &ManifestVersionInfo, root: &Path) -> Result<PathBuf> {
        let natives_dir = root.join("natives");
        std::fs::create_dir_all(&natives_dir)?;
        Ok(natives_dir)
    }

    fn build_args(&self, info: &ManifestVersionInfo, req: &LaunchRequest, game_dir: &Path, assets_dir: &Path, natives_dir: &Path, memory: u32) -> (Vec<String>, Vec<String>, String) {
        let tokens = vec![
            ("auth_player_name".to_string(), req.account_name.clone()),
            ("auth_uuid".to_string(), req.account_uuid.clone()),
            ("auth_access_token".to_string(), "0".to_string()),
            ("version_name".to_string(), info.id.clone()),
            ("version_type".to_string(), info.version_type.clone()),
            ("game_directory".to_string(), game_dir.to_string_lossy().to_string()),
            ("assets_root".to_string(), assets_dir.to_string_lossy().to_string()),
            ("assets_index_name".to_string(), info.asset_index.id.clone()),
            ("launcher_name".to_string(), "EraLauncher".to_string()),
            ("launcher_version".to_string(), "0.1.0".to_string()),
            ("natives_directory".to_string(), natives_dir.to_string_lossy().to_string()),
            ("resolution_width".to_string(), "854".to_string()),
            ("resolution_height".to_string(), "480".to_string()),
        ];

        let jvm_args = ArgumentBuilder::build_jvm_args(&["-Xmx${MAX_MEMORY}M".to_string(), "-Duser.language=en".to_string()], memory);
        let game_args = vec!["--username".to_string(), "${auth_player_name}".to_string(), "--version".to_string(), "${version_name}".to_string(), "--gameDir".to_string(), "${game_directory}".to_string(), "--assetsDir".to_string(), "${assets_root}".to_string()];

        let jvm_args = ArgumentBuilder::substitute_tokens(&jvm_args, &tokens);
        let game_args = ArgumentBuilder::substitute_tokens(&game_args, &tokens);
        let main_class = info.main_class.clone().unwrap_or_else(|| "net.minecraft.client.main.Main".to_string());

        (jvm_args, game_args, main_class)
    }

    fn build_classpath(&self, root: &Path, info: &ManifestVersionInfo, natives_dir: &Path) -> String {
        let mut parts = vec![root.join("versions").join(&info.id).join(format!("{}.jar", info.id))];
        let libs_dir = root.join("libraries");
        for lib in &info.libraries {
            if !self.library_applies(&lib.rules) { continue; }
            parts.push(self.resolve_library_path(&lib.name, &libs_dir));
        }
        if natives_dir.exists() {
            parts.push(natives_dir.to_path_buf());
        }
        let sep = if cfg!(windows) { ";" } else { ":" };
        parts.iter().map(|p| p.to_string_lossy().to_string()).collect::<Vec<_>>().join(sep)
    }

    fn resolve_library_path(&self, name: &str, base: &Path) -> PathBuf {
        let parts: Vec<&str> = name.split(':').collect();
        if parts.len() >= 3 {
            let group = parts[0].replace('.', "/");
            let artifact = parts[1];
            let version = parts[2];
            let classifier = parts.get(3).map(|s| format!("-{}", s)).unwrap_or_default();
            base.join(group).join(artifact).join(version).join(format!("{}-{}{}.jar", artifact, version, classifier))
        } else {
            base.join(name.replace(':', "/")).with_extension("jar")
        }
    }

    fn library_applies(&self, rules: &Option<serde_json::Value>) -> bool {
        let Some(rules) = rules else { return true; };
        let arr = match rules.as_array() { Some(a) => a, None => return true };
        let mut allowed = false;
        let mut matched = false;
        for rule in arr {
            let obj = match rule.as_object() { Some(o) => o, None => continue };
            let action = obj.get("action").and_then(|a| a.as_str()).unwrap_or("allow");
            let os = obj.get("os").and_then(|o| o.as_object());
            let mut ok = true;
            if let Some(os) = os {
                if let Some(name) = os.get("name").and_then(|n| n.as_str()) {
                    let current = match std::env::consts::OS { "windows" => "windows", "macos" => "osx", _ => "linux" };
                    if current != name { ok = false; }
                }
            }
            matched = true;
            if ok { allowed = action == "allow"; }
        }
        matched && allowed
    }
}
