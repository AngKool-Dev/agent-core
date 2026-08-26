import { invoke } from "@tauri-apps/api/core";
import type {
  Config,
  InstanceConfig,
  ModrinthProject,
  ModrinthVersion,
  JavaInstallation,
  LaunchResult,
} from "./types";

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

export async function prepareInstance(instance: InstanceConfig, instancesDir: string): Promise<void> {
  return invoke("prepare_instance", { instance, instancesDir });
}

export async function getAllVersions(): Promise<string[]> {
  return invoke("get_versions");
}

export async function launchInstance(
  req: {
    instance_id: string;
    account_name: string;
    account_uuid: string;
    java_path?: string;
    minecraft_dir?: string;
    fresh: boolean;
    memory: number;
    game_version: string;
    loader: string;
    loader_version?: string;
  },
  instancesDir: string
): Promise<LaunchResult> {
  return invoke("launch_instance", { req, instancesDir });
}

export async function searchModrinth(params: {
  query: string;
  contentType: string;
  gameVersion: string;
  loader: string;
}): Promise<ModrinthProject[]> {
  return invoke("search_modrinth", params);
}

export async function getModVersions(projectId: string): Promise<ModrinthVersion[]> {
  return invoke("get_mod_versions", { projectId });
}

export async function installMod(params: {
  projectId: string;
  versionId: string;
  fileUrl: string;
  fileName: string;
  instanceId: string;
  contentType: string;
  instancesDir: string;
}): Promise<void> {
  return invoke("install_mod", params);
}

export async function getFabricLoaderVersions(gameVersion: string): Promise<string[]> {
  return invoke("get_fabric_loader_versions", { gameVersion });
}

export async function getForgeVersions(gameVersion: string): Promise<string[]> {
  return invoke("get_forge_versions", { gameVersion });
}

export async function getJavaInstallations(): Promise<JavaInstallation[]> {
  return invoke("get_java_installations");
}

export async function getInstancesDir(): Promise<string> {
  return invoke("get_instances_dir");
}

export async function getInstallerInfo(): Promise<{
  install_dir: string;
  java_detected: { required_major: number; found: number | null };
  java_installations: { path: string; version: number | null }[];
}> {
  return invoke("get_installer_info");
}

export async function installJavaRuntime(javaVersion: number): Promise<string | null> {
  return invoke("install_java_runtime", { javaVersion });
}
