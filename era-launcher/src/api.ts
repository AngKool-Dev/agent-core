import { invoke } from "@tauri-apps/api/core";
import type {
  Config,
  InstanceConfig,
  Account,
  LaunchState,
  DownloadProgress,
  ModrinthProject,
  ModrinthVersion,
  JavaInstallation,
  Page,
} from "../types";

export async function getConfig(): Promise<Config> {
  return invoke("get_config");
}

export async function saveConfig(config: Config): Promise<void> {
  return invoke("save_config", { config });
}

export async function listInstances(): Promise<InstanceConfig[]> {
  return invoke("list_instances");
}

export async function createInstance(instance: InstanceConfig): Promise<InstanceConfig> {
  return invoke("create_instance", { instance });
}

export async function deleteInstance(id: string): Promise<boolean> {
  return invoke("delete_instance", { id });
}

export async function updateInstance(instance: InstanceConfig): Promise<boolean> {
  return invoke("update_instance", { instance });
}

export async function scanVersions(): Promise<any[]> {
  return invoke("scan_versions");
}

export async function getVersions(): Promise<string[]> {
  return invoke("get_versions");
}

export async function launchInstance(req: {
  instance_id: string;
  account_name: string;
  account_uuid: string;
  java_path?: string;
  minecraft_dir?: string;
  fresh: boolean;
  memory: number;
  game_version: string;
}): Promise<any> {
  return invoke("launch_instance", { req });
}

export async function searchModrinth(params: {
  query: string;
  content_type: string;
  game_version: string;
  loader: string;
}): Promise<ModrinthProject[]> {
  return invoke("search_modrinth", params);
}

export async function getModVersions(projectId: string): Promise<ModrinthVersion[]> {
  return invoke("get_mod_versions", { projectId });
}

export async function installMod(params: {
  project_id: string;
  version_id: string;
  file_url: string;
  file_name: string;
  instance_id: string;
  content_type: string;
}): Promise<void> {
  return invoke("install_mod", params);
}

export async function getJavaInstallations(): Promise<JavaInstallation[]> {
  return invoke("get_java_installations");
}

export async function getLauncherConfigDir(): Promise<string> {
  return invoke("get_launcher_config_dir");
}
