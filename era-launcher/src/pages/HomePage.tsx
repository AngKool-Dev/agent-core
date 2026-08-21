import { useState, useEffect } from "react";
import type { Config, LaunchState } from "../types";
import { launchInstance, getJavaInstallations } from "../api";

interface HomePageProps {
  config: Config;
  refreshConfig: () => void;
  launchState: LaunchState;
  setLaunchState: (s: LaunchState) => void;
}

export default function HomePage({ config, launchState, setLaunchState }: HomePageProps) {
  const [selectedAccount, setSelectedAccount] = useState<string>(config.default_account || config.accounts[0]?.uuid || "");
  const [consoleLog, setConsoleLog] = useState<string[]>([]);
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
      setConsoleLog((prev) => [...prev, "No account selected"]);
      return;
    }
    setLaunchState({ status: "launching" });
    setConsoleLog((prev) => [...prev, `Launching ${instance.name}...`]);
    try {
      const result = await launchInstance({
        instance_id: instance.id,
        account_name: account.name,
        account_uuid: account.uuid,
        java_path: instance.java,
        minecraft_dir: instance.minecraft_dir,
        fresh: false,
        memory: instance.memory,
        game_version: instance.game_version,
      });
      setLaunchState({ status: result.success ? "finished" : "failed", exitCode: result.exit_code, message: result.message });
      setConsoleLog((prev) => [...prev, result.message]);
    } catch (e) {
      setLaunchState({ status: "failed", message: String(e) });
      setConsoleLog((prev) => [...prev, `Error: ${e}`]);
    }
  };

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
              </button>
            ))}
          </div>
        )}
      </div>
      {consoleLog.length > 0 && (
        <div className="card console-card">
          <h3>Console Output</h3>
          <div className="console-output">
            {consoleLog.map((line, i) => (
              <div key={i} className="console-line">{line}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
