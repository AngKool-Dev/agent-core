export interface Account {
  id: string;
  name: string;
  uuid: string;
  type: "offline" | "microsoft";
  access_token?: string;
  created_at: number;
  last_used?: number;
}

export interface InstanceConfig {
  id: string;
  name: string;
  game_version: string;
  loader: string;
  loader_version?: string;
  memory: number;
  java?: string;
  game_dir?: string;
  resolution_width?: number;
  resolution_height?: number;
  account_uuid?: string;
  minecraft_dir?: string;
}

export interface Settings {
  default_memory: number;
  java_path?: string;
  theme: "dark" | "light" | "system";
  language: string;
}

export interface WindowConfig {
  width: number;
  height: number;
  maximized: boolean;
}

export interface Config {
  settings: Settings;
  instances: InstanceConfig[];
  accounts: Account[];
  window: WindowConfig;
  default_account?: string;
}

export interface LaunchState {
  status: "idle" | "launching" | "running" | "finished" | "failed" | "stopped";
  exitCode?: number;
  message?: string;
}

export interface LaunchResult {
  success: boolean;
  pid: number | null;
  exit_code: number | null;
  message: string;
  java_path: string | null;
}

export interface DownloadProgress {
  file: string;
  bytes_downloaded: number;
  total_bytes: number | null;
  is_complete: boolean;
}

export interface ModrinthProject {
  id: string;
  title: string;
  description: string;
  icon_url?: string;
  downloads: number;
  author: string;
  categories: string[];
  gallery: string[];
  versions: string[];
  game_versions: string[];
  loaders: string[];
}

export interface ModrinthVersion {
  id: string;
  project_id: string;
  version_number: string;
  game_versions: string[];
  loaders: string[];
  files: ModrinthFile[];
}

export interface ModrinthFile {
  url: string;
  filename: string;
  size: number;
  file_type?: string;
}

export interface JavaInstallation {
  path: string;
  version?: { major: number };
}

export type Page = "home" | "instances" | "mods" | "settings" | "accounts" | "install";

export interface InstallProgress {
  step: string;
  message: string;
  progress: number;
  is_complete: boolean;
}

export interface InstallerInfo {
  install_dir: string;
  java_detected: { required_major: number; found: number | null };
  java_installations: JavaInstallationInfo[];
}

export interface JavaInstallationInfo {
  path: string;
  version: number | null;
}
