import { useState, useEffect } from "react";
import type { InstallerInfo, InstallProgress } from "../types";
import { getInstallerInfo, installJavaRuntime } from "../api";

export default function InstallPage() {
  const [installerInfo, setInstallerInfo] = useState<InstallerInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [progress, setProgress] = useState<InstallProgress | null>(null);

  useEffect(() => {
    loadInstallerInfo();
  }, []);

  const loadInstallerInfo = async () => {
    setLoading(true);
    try {
      const info = await getInstallerInfo();
      setInstallerInfo(info);
    } catch (err) {
      console.error("Failed to load installer info:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async () => {
    setInstalling(true);
    setProgress(null);

    try {
      const requiredVersion = installerInfo?.java_detected.required_major || 21;
      setProgress({
        step: "DOWNLOADING",
        message: `Downloading Java ${requiredVersion}...`,
        progress: 0,
        is_complete: false,
      });
      const path = await installJavaRuntime(requiredVersion);
      if (path) {
        setProgress({
          step: "COMPLETE",
          message: `Java ${requiredVersion} installed to ${path}`,
          progress: 100,
          is_complete: true,
        });
      } else {
        setProgress({
          step: "ERROR",
          message: "Java installation returned no path",
          progress: 100,
          is_complete: true,
        });
      }
    } catch (err) {
      console.error("Install failed:", err);
      setProgress({
        step: "error",
        message: `Installation failed: ${err}`,
        progress: 100,
        is_complete: true,
      });
    } finally {
      setInstalling(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading installer information...</div>;
  }

  return (
    <div className="install-page">
      <div className="install-header">
        <h1>Web Installer</h1>
        <p>Install EraLauncher with optional Java auto-download</p>
      </div>

      {installerInfo && (
        <div className="install-info">
          <div className="info-section">
            <h3>Installation Directory</h3>
            <code className="path">{installerInfo.install_dir}</code>
          </div>

          <div className="info-section">
            <h3>Java Status</h3>
            <div className="java-status">
              <div>
                Required: Java {installerInfo.java_detected.required_major}+
              </div>
              <div>
                Detected:{" "}
                {installerInfo.java_detected.found
                  ? `Java ${installerInfo.java_detected.found}`
                  : "Not found"}
              </div>
              <div className="installations">
                {installerInfo.java_installations.length > 0 ? (
                  installerInfo.java_installations.map((inst, i) => (
                    <div key={i} className="java-install">
                      {inst.version
                        ? `Java ${inst.version} at ${inst.path}`
                        : inst.path}
                    </div>
                  ))
                ) : (
                  <span>No Java installations found</span>
                )}
              </div>
            </div>
          </div>

          {!installerInfo.java_detected.found && (
            <div className="warning">
              <strong>Warning:</strong> Java {installerInfo.java_detected.required_major}+ is
              required for Minecraft. The installer will download it automatically unless you
              uncheck "Install Java".
            </div>
          )}
        </div>
      )}

      {progress && (
        <div className="install-progress">
          <h3>
            {progress.step}: {progress.message}
          </h3>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${Math.min(progress.progress, 100)}%` }}
            />
          </div>
          <span className="progress-text">{Math.round(progress.progress)}%</span>
        </div>
      )}

      <div className="install-actions">
        <button
          type="button"
          className="btn-primary"
          onClick={handleInstall}
          disabled={installing}
        >
          {installing ? "Installing..." : "Install EraLauncher"}
        </button>
        <button type="button" className="btn-secondary" onClick={loadInstallerInfo}>
          Refresh Status
        </button>
      </div>

      <style>{`
        .install-page {
          padding: 24px;
          max-width: 720px;
          margin: 0 auto;
        }
        .install-header h1 {
          margin: 0 0 8px 0;
          font-size: 24px;
        }
        .install-header p {
          margin: 0 0 24px 0;
          color: var(--muted-foreground);
        }
        .info-section {
          margin-bottom: 20px;
          padding: 16px;
          background: var(--card);
          border: 1px solid var(--border);
          border-radius: 8px;
        }
        .info-section h3 {
          margin: 0 0 8px 0;
          font-size: 14px;
          font-weight: 600;
        }
        .path {
          font-family: monospace;
          font-size: 13px;
          color: var(--accent);
        }
        .java-status div {
          margin-bottom: 4px;
          font-size: 14px;
        }
        .java-install {
          font-size: 13px;
          color: var(--muted-foreground);
          margin-top: 4px;
        }
        .warning {
          background: rgba(255, 200, 0, 0.1);
          border: 1px solid rgba(255, 200, 0, 0.3);
          padding: 12px;
          border-radius: 6px;
          margin-top: 12px;
        }
        .install-progress {
          margin: 24px 0;
          padding: 16px;
          background: var(--card);
          border: 1px solid var(--border);
          border-radius: 8px;
        }
        .install-progress h3 {
          margin: 0 0 12px 0;
          font-size: 16px;
        }
        .progress-bar {
          width: 100%;
          height: 20px;
          background: var(--muted);
          border-radius: 10px;
          overflow: hidden;
          margin-bottom: 4px;
        }
        .progress-fill {
          height: 100%;
          background: var(--accent);
          transition: width 0.3s ease;
        }
        .progress-text {
          font-size: 12px;
          color: var(--muted-foreground);
        }
        .install-actions {
          margin-top: 24px;
          display: flex;
          gap: 12px;
        }
        .btn-primary, .btn-secondary {
          padding: 10px 20px;
          border-radius: 6px;
          border: 1px solid var(--border);
          background: var(--card);
          cursor: pointer;
          font-size: 14px;
          transition: background 0.2s;
        }
        .btn-primary:hover {
          background: var(--accent);
          color: var(--accent-foreground);
        }
        .btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .btn-secondary:hover {
          background: var(--muted);
        }
        .loading {
          padding: 40px;
          text-align: center;
          color: var(--muted-foreground);
        }
      `}</style>
    </div>
  );
}
