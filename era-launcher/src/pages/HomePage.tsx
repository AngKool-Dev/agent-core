import { useState, useEffect, type Dispatch, type SetStateAction } from "react";
import type { Config, LaunchState, DownloadProgress } from "../types";
import { launchInstance, getJavaInstallations, updateInstance } from "../api";

interface HomePageProps {
  config: Config;
  refreshConfig: () => void;
  launchState: LaunchState;
  setLaunchState: Dispatch<SetStateAction<LaunchState>>;
  instancesDir: string;
  consoleLines: string[];
  setConsoleLines: Dispatch<SetStateAction<string[]>>;
  downloadProgress: DownloadProgress | null;
}

export default function HomePage({ config, refreshConfig, launchState, setLaunchState, instancesDir, consoleLines, setConsoleLines, downloadProgress }: HomePageProps) {
  const [selectedAccount, setSelectedAccount] = useState<string>(config.default_account || config.accounts[0]?.uuid || "");
  const [javaLabel, setJavaLabel] = useState("Detecting...");

  useEffect(() => {
    getJavaInstallations().then((installations) => {
      if (installations.length > 0 && installations[0].version) {
        setJavaLabel(`Java ${installations[0].version!.major} (${installations[0].path.split("\\").slice(-2).join("\\")})`);
      } else {
        setJavaLabel("Not found");
      }
    });
  }, []);

  const handleLaunch = async (instanceId: string) => {
    const instance = config.instances.find((i) => i.id === instanceId);
    if (!instance) return;
    const account = config.accounts.find((a) => a.uuid === selectedAccount) || config.accounts[0];
    if (!account) {
      setConsoleLines((prev) => [...prev, "No account selected"]);
      return;
    }
    setLaunchState({ status: "launching" });
    setConsoleLines((prev) => [...prev, `Launching ${instance.name}...`]);
    try {
        const result = await launchInstance(
         {
            instance_id: instance.id,
            account_name: account.name,
            account_uuid: account.uuid,
            java_path: instance.java,
            minecraft_dir: instance.minecraft_dir,
            fresh: false,
            memory: instance.memory,
            game_version: instance.game_version,
            loader: instance.loader,
            loader_version: instance.loader_version,
          },
          instancesDir
        );
      setConsoleLines((prev) => [...prev, result.message]);
      if (result.success && result.java_path && result.java_path !== instance.java) {
        const updated = { ...instance, java: result.java_path };
        await updateInstance(updated);
        refreshConfig();
      }
    } catch (e) {
      setLaunchState({ status: "failed", message: String(e) });
      setConsoleLines((prev) => [...prev, `Error: ${e}`]);
    }
  };

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Welcome to EraLauncher</h2>
        <p className="subtitle">Your modern Minecraft launcher</p>
      </div>
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-value">{config.instances.length}</div>
          <div className="stat-label">Instances</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{config.accounts.length}</div>
          <div className="stat-label">Accounts</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{javaLabel}</div>
          <div className="stat-label">Java</div>
        </div>
      </div>
      <div className="card">
        <h3>Quick Launch</h3>
        {launchState.status !== "idle" && (
          <div className="status-banner">
            Status: <strong>{launchState.status.toUpperCase()}</strong>
            {launchState.message && <span className="status-message">{launchState.message}</span>}
          </div>
        )}
        {downloadProgress && !downloadProgress.is_complete && downloadProgress.total_bytes && (
          <div className="download-progress">
            <div className="download-progress-bar">
              <div
                className="download-progress-fill"
                style={{
                  width: `${(downloadProgress.bytes_downloaded / downloadProgress.total_bytes) * 100}%`,
                }}
              />
            </div>
            <span className="download-filename">{downloadProgress.file}</span>
            <span className="download-bytes">
              {formatBytes(downloadProgress.bytes_downloaded)} /{" "}
              {formatBytes(downloadProgress.total_bytes)}
            </span>
          </div>
        )}
        {config.accounts.length > 0 && (
          <div className="form-group">
            <label>Account</label>
            <select value={selectedAccount} onChange={(e) => setSelectedAccount(e.target.value)}>
              {config.accounts.map((a) => (
                <option key={a.uuid} value={a.uuid}>{a.name}</option>
              ))}
            </select>
          </div>
        )}
        {config.instances.length === 0 ? (
          <p className="empty-text">No instances yet. Create one to get started!</p>
        ) : (
          <div className="instance-list">
            {config.instances.map((inst) => (
              <button
                key={inst.id}
                className="btn btn-primary launch-btn"
                disabled={launchState.status === "launching" || launchState.status === "running"}
                onClick={() => handleLaunch(inst.id)}
              >
                ▶ Launch {inst.name}
                <span className="instance-meta">v{inst.game_version} | {(inst.memory / 1024).toFixed(1)} GB</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {consoleLines.length > 0 && (
        <div className="card console-card">
          <h3>Console Output</h3>
          <div className="console-output">
            {consoleLines.map((line, i) => (
              <div key={i} className="console-line">{line}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
