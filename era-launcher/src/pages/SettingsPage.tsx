import { useState, useEffect } from "react";
import type { Config } from "../types";
import { saveConfig, getJavaInstallations } from "../api";

interface SettingsPageProps {
  config: Config;
  refreshConfig: () => void;
}

export default function SettingsPage({ config, refreshConfig }: SettingsPageProps) {
  const [memory, setMemory] = useState(config.settings.default_memory);
  const [theme, setTheme] = useState<"dark" | "light" | "system">(config.settings.theme as any);
  const [javaPath, setJavaPath] = useState(config.settings.java_path || "");
  const [defaultAccount, setDefaultAccount] = useState(config.default_account || config.accounts[0]?.uuid || "");

  useEffect(() => {
    setMemory(config.settings.default_memory);
    setTheme(config.settings.theme as any);
    setJavaPath(config.settings.java_path || "");
    setDefaultAccount(config.default_account || config.accounts[0]?.uuid || "");
  }, [config]);

  const handleSave = async () => {
    const updated: Config = {
      ...config,
      settings: { ...config.settings, default_memory: memory, theme, java_path: javaPath || undefined },
      default_account: defaultAccount || undefined,
    };
    await saveConfig(updated);
    refreshConfig();
  };

  const handleBrowseJava = async () => {
    const installations = await getJavaInstallations();
    if (installations.length > 0) {
      setJavaPath(installations[0].path);
    }
  };

  return (
    <div className="page">
      <h2>Settings</h2>
      <div className="settings-section">
        <h3>Memory</h3>
        <div className="form-group">
          <label>Maximum Memory (MB)</label>
          <input type="range" min="1024" max="16384" step="1024" value={memory} onChange={(e) => setMemory(Number(e.target.value))} />
          <span>{memory / 1024} GB</span>
        </div>
      </div>
      <div className="settings-section">
        <h3>Java</h3>
        <div className="form-group">
          <label>Java Path</label>
          <input value={javaPath} onChange={(e) => setJavaPath(e.target.value)} placeholder="Auto-detect" />
          <button className="btn btn-secondary" onClick={handleBrowseJava}>Browse</button>
        </div>
      </div>
      <div className="settings-section">
        <h3>Appearance</h3>
        <div className="form-group">
          <label>Theme</label>
          <div className="radio-group">
            {(["dark", "light", "system"] as const).map((t) => (
              <label key={t} className="radio-label">
                <input type="radio" name="theme" checked={theme === t} onChange={() => setTheme(t)} />
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </label>
            ))}
          </div>
        </div>
      </div>
      <div className="settings-section">
        <h3>Default Account</h3>
        <div className="form-group">
          <select value={defaultAccount} onChange={(e) => setDefaultAccount(e.target.value)}>
            {config.accounts.map((a) => (
              <option key={a.uuid} value={a.uuid}>{a.name}</option>
            ))}
          </select>
        </div>
      </div>
      <button className="btn btn-primary" onClick={handleSave}>Save Settings</button>
    </div>
  );
}
